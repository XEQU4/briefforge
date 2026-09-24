from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import commit_or_rollback, get_db
from app.models import ClarifyingQuestion, Task
from app.schemas import AnswersSubmit, TaskCreate, TaskRead, TaskUpdate, TaskWithQuestions
from app.services.ai_client import GENERATED_CARD_FIELDS, build_card_from_answers, get_clarifying_questions
from app.services.rating import calculate_rating, readiness_for_score

router = APIRouter(tags=["tasks"])

TASK_STATUSES = {"draft", "clarifying", "card_ready", "confirmed"}
SUGGESTIONS = {
    "context": "Describe the business context and current situation",
    "need": "State the specific need or problem to solve",
    "data_materials": "List available data, materials, and access conditions",
    "expected_result": "Describe the expected result or deliverable",
    "success_criteria": "Define measurable success criteria",
    "constraints": "List constraints such as time, tools, or compliance",
    "users": "Identify the users or beneficiaries",
    "contact": "Provide a business contact",
    "interaction_format": "Specify how the team can interact with the business",
}


async def _get_task(task_id: int, db: AsyncSession) -> Task:
    result = await db.execute(select(Task).options(selectinload(Task.questions)).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _normalize_answers(questions: list[ClarifyingQuestion], incoming: list[str] | dict[str, str]) -> dict[str, str]:
    ordered_questions = sorted(questions, key=lambda question: question.order)
    resolved: dict[int, str] = {}
    if isinstance(incoming, list):
        if len(incoming) != len(ordered_questions):
            raise HTTPException(status_code=422, detail="Provide one answer for each clarification question")
        resolved = {question.id: answer for question, answer in zip(ordered_questions, incoming)}
    else:
        by_id = {str(question.id): question for question in ordered_questions}
        text_matches: dict[str, list[ClarifyingQuestion]] = {}
        for question in ordered_questions:
            text_matches.setdefault(question.question_text, []).append(question)
        for key, answer in incoming.items():
            matches: dict[int, ClarifyingQuestion] = {}
            if key in by_id:
                question = by_id[key]
                matches[question.id] = question
            for question in text_matches.get(key, []):
                matches[question.id] = question
            if not matches:
                raise HTTPException(status_code=422, detail="Answer keys must match a question id or question text")
            if len(matches) != 1:
                raise HTTPException(status_code=422, detail="Answer key ambiguously matches multiple questions")
            question_id = next(iter(matches))
            previous = resolved.get(question_id)
            if previous is not None and previous != answer:
                raise HTTPException(status_code=422, detail="Conflicting answers were provided for the same question")
            resolved[question_id] = answer

    # Partial submissions update only addressed questions and retain prior answers.
    complete = {
        question.id: question.answer_text or ""
        for question in ordered_questions
    }
    complete.update(resolved)
    return {question.question_text: complete[question.id] for question in ordered_questions}


@router.post("/tasks", response_model=TaskWithQuestions, status_code=201)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    # Network work happens before the first database write.
    questions = await get_clarifying_questions(payload.draft_text, payload.topic)
    task = Task(context=payload.draft_text, topic=payload.topic, status="clarifying", questions=[])
    db.add(task)
    task.questions.extend(
        ClarifyingQuestion(question_text=question_text, order=index)
        for index, question_text in enumerate(questions, 1)
    )
    await commit_or_rollback(db)
    task = await _get_task(task.id, db)
    return {"task": task, "questions": task.questions}


@router.patch("/tasks/{task_id}/answers", response_model=TaskRead)
async def answer_task(task_id: int, payload: AnswersSubmit, db: AsyncSession = Depends(get_db)):
    task = await _get_task(task_id, db)
    if task.status not in {"clarifying", "card_ready"}:
        raise HTTPException(status_code=409, detail="Answers can only be submitted while the task is clarifying or card_ready")
    questions = sorted(task.questions, key=lambda q: q.order)
    answers_by_text = _normalize_answers(questions, payload.answers)
    question_texts = [question.question_text for question in questions]
    card = await build_card_from_answers(task.context or "", question_texts, answers_by_text)
    for field, value in card.items():
        if (
            field in GENERATED_CARD_FIELDS
            and isinstance(value, str)
            and value.strip()
            and not (isinstance(getattr(task, field), str) and getattr(task, field).strip())
        ):
            setattr(task, field, value)
    for question in questions:
        question.answer_text = answers_by_text[question.question_text]
    task.status = "card_ready"
    await commit_or_rollback(db)
    return await _get_task(task.id, db)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(task_id: int, payload: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await _get_task(task_id, db)
    updates = payload.model_dump(exclude_unset=True)
    requested_status = updates.pop("status", None)
    if requested_status is not None:
        if requested_status not in TASK_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid task status")
        if requested_status != task.status:
            raise HTTPException(status_code=409, detail="Use the answers or confirm endpoint to change task status")
    for field, value in updates.items():
        setattr(task, field, value)
    if updates and task.status == "confirmed":
        score, breakdown, _ = calculate_rating(task)
        task.rating_score = score
        task.rating_breakdown = breakdown
        task.readiness_level = readiness_for_score(score)
    await commit_or_rollback(db)
    return await _get_task(task.id, db)


@router.post("/tasks/{task_id}/confirm", response_model=TaskRead)
async def confirm_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await _get_task(task_id, db)
    if task.status != "card_ready" and task.status != "confirmed":
        raise HTTPException(status_code=409, detail="Task must have an editable card before confirmation")
    score, breakdown, _ = calculate_rating(task)
    task.rating_score = score
    task.rating_breakdown = breakdown
    task.readiness_level = readiness_for_score(score)
    task.status = "confirmed"
    await commit_or_rollback(db)
    return await _get_task(task.id, db)


@router.get("/tasks/{task_id}/rating")
async def task_rating(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await _get_task(task_id, db)
    score, breakdown, missing = calculate_rating(task)
    return {"score": score, "readiness_level": readiness_for_score(score), "breakdown": breakdown,
            "missing_fields": missing, "suggestions": [SUGGESTIONS[field] for field in missing]}


@router.get("/tasks", response_model=list[TaskRead])
async def list_tasks(topic: str | None = None, readiness_level: str | None = None, sort: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    if sort not in (None, "rating"):
        raise HTTPException(status_code=422, detail="sort must be 'rating'")
    if readiness_level is not None and readiness_level not in {"draft", "working", "ready", "priority"}:
        raise HTTPException(status_code=422, detail="Invalid readiness_level")
    query = select(Task).where(Task.status == "confirmed")
    if topic:
        query = query.where(Task.topic == topic)
    if readiness_level:
        query = query.where(Task.readiness_level == readiness_level)
    if sort == "rating":
        query = query.order_by(Task.rating_score.desc())
    result = await db.execute(query)
    return list(result.scalars().all())
