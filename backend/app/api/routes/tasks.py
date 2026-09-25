from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import commit_or_rollback, get_db
from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.dependencies.authorization import require_organization_member, require_task_organization_member
from app.domain.status import TaskStatus
from app.models import ClarifyingQuestion, OrganizationMember, Task, User
from app.schemas import AnswersSubmit, TaskCreate, TaskRead, TaskUpdate, TaskWithQuestions
from app.schemas.pagination import PaginatedResponse
from app.services.ai_client import GENERATED_CARD_FIELDS, build_card_from_answers, get_clarifying_questions
from app.services.lifecycle import InvalidTransition, transition_task
from app.services.rating import calculate_rating, readiness_for_score

router = APIRouter(tags=["tasks"])
legacy_list_router = APIRouter(tags=["tasks"])
versioned_list_router = APIRouter(tags=["tasks"])

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
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.organization_id is None:
        organization_ids = list(
            (await db.scalars(
                select(OrganizationMember.organization_id)
                .where(OrganizationMember.user_id == user.id)
                .order_by(OrganizationMember.organization_id)
            )).all()
        )
        if not organization_ids:
            raise HTTPException(status_code=409, detail="Create or join an organization before creating tasks")
        if len(organization_ids) > 1:
            raise HTTPException(status_code=409, detail="organization_id is required when you belong to multiple organizations")
        organization_id = organization_ids[0]
    else:
        organization_id = payload.organization_id
        await require_organization_member(organization_id, user, db)

    # Network work happens before the first database write.
    questions = await get_clarifying_questions(payload.draft_text, payload.topic)
    task = Task(
        context=payload.draft_text,
        topic=payload.topic,
        status=TaskStatus.CLARIFYING,
        organization_id=organization_id,
        created_by_user_id=user.id,
        questions=[],
    )
    db.add(task)
    task.questions.extend(
        ClarifyingQuestion(question_text=question_text, order=index)
        for index, question_text in enumerate(questions, 1)
    )
    await commit_or_rollback(db)
    task = await _get_task(task.id, db)
    return {"task": task, "questions": task.questions}


@router.patch("/tasks/{task_id}/answers", response_model=TaskRead)
async def answer_task(
    task_id: int,
    payload: AnswersSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await _get_task(task_id, db)
    await require_task_organization_member(task, user, db)
    try:
        next_status = transition_task(task.status, TaskStatus.CARD_READY)
    except InvalidTransition:
        raise HTTPException(status_code=409, detail="Answers can only be submitted while the task is clarifying or card_ready")
    task.status = next_status
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
    await commit_or_rollback(db)
    return await _get_task(task.id, db)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await _get_task(task_id, db)
    await require_task_organization_member(task, user, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(task, field, value)
    if updates and task.status == TaskStatus.CONFIRMED:
        score, breakdown, _ = calculate_rating(task)
        task.rating_score = score
        task.rating_breakdown = breakdown
        task.readiness_level = readiness_for_score(score)
    await commit_or_rollback(db)
    return await _get_task(task.id, db)


@router.post("/tasks/{task_id}/confirm", response_model=TaskRead)
async def confirm_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await _get_task(task_id, db)
    await require_task_organization_member(task, user, db)
    try:
        next_status = transition_task(task.status, TaskStatus.CONFIRMED)
    except InvalidTransition:
        raise HTTPException(status_code=409, detail="Task must have an editable card before confirmation")
    score, breakdown, _ = calculate_rating(task)
    task.rating_score = score
    task.rating_breakdown = breakdown
    task.readiness_level = readiness_for_score(score)
    task.status = next_status
    await commit_or_rollback(db)
    return await _get_task(task.id, db)


@router.get("/tasks/{task_id}/rating")
async def task_rating(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    task = await _get_task(task_id, db)
    if task.status != TaskStatus.CONFIRMED:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        await require_task_organization_member(task, user, db)
    score, breakdown, missing = calculate_rating(task)
    return {"score": score, "readiness_level": readiness_for_score(score), "breakdown": breakdown,
            "missing_fields": missing, "suggestions": [SUGGESTIONS[field] for field in missing]}


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    task = await _get_task(task_id, db)
    if task.status != TaskStatus.CONFIRMED:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        await require_task_organization_member(task, user, db)
    return task


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _list_tasks(
    *,
    versioned: bool,
    topic: str | None = None,
    readiness_level: str | None = None,
    sort: str | None = None,
    q: str | None = None,
    min_rating: int | None = None,
    max_rating: int | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession,
):
    allowed_sorts = {None, "rating", "newest", "oldest"} if versioned else {None, "rating"}
    if sort not in allowed_sorts:
        supported = "rating, newest, or oldest" if versioned else "rating"
        raise HTTPException(status_code=422, detail=f"sort must be {supported}")
    if readiness_level is not None and readiness_level not in {"draft", "working", "ready", "priority"}:
        raise HTTPException(status_code=422, detail="Invalid readiness_level")
    if min_rating is not None and max_rating is not None and min_rating > max_rating:
        raise HTTPException(status_code=422, detail="min_rating must be less than or equal to max_rating")

    filters = [Task.status == TaskStatus.CONFIRMED]
    if topic:
        filters.append(Task.topic == topic)
    if readiness_level:
        filters.append(Task.readiness_level == readiness_level)
    if min_rating is not None:
        filters.append(Task.rating_score >= min_rating)
    if max_rating is not None:
        filters.append(Task.rating_score <= max_rating)
    normalized_q = (q or "").strip()
    if normalized_q:
        pattern = f"%{_escape_like(normalized_q)}%"
        filters.append(or_(
            Task.title.ilike(pattern, escape="\\"),
            Task.context.ilike(pattern, escape="\\"),
            Task.need.ilike(pattern, escape="\\"),
            Task.expected_result.ilike(pattern, escape="\\"),
            Task.topic.ilike(pattern, escape="\\"),
        ))

    query = select(Task).where(*filters)
    effective_sort = sort if sort is not None else ("newest" if versioned else None)
    if effective_sort == "rating":
        query = query.order_by(Task.rating_score.desc(), Task.id.asc())
    elif effective_sort == "newest":
        query = query.order_by(Task.created_at.desc(), Task.id.desc())
    elif effective_sort == "oldest":
        query = query.order_by(Task.created_at.asc(), Task.id.asc())

    if not versioned:
        result = await db.execute(query)
        return list(result.scalars().all())

    total = await db.scalar(select(func.count()).select_from(Task).where(*filters)) or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = list(result.scalars().all())
    return PaginatedResponse[TaskRead].build(items, page, page_size, total)


@legacy_list_router.get("/tasks", response_model=list[TaskRead])
async def list_tasks_legacy(
    topic: str | None = None,
    readiness_level: str | None = None,
    sort: str | None = Query(None),
    q: str | None = Query(None, max_length=200),
    min_rating: int | None = Query(None, ge=0, le=100),
    max_rating: int | None = Query(None, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await _list_tasks(
        versioned=False,
        topic=topic,
        readiness_level=readiness_level,
        sort=sort,
        q=q,
        min_rating=min_rating,
        max_rating=max_rating,
        db=db,
    )


@versioned_list_router.get("/tasks", response_model=PaginatedResponse[TaskRead])
async def list_tasks_v1(
    topic: str | None = None,
    readiness_level: str | None = None,
    sort: str | None = Query(None),
    q: str | None = Query(None, max_length=200),
    min_rating: int | None = Query(None, ge=0, le=100),
    max_rating: int | None = Query(None, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await _list_tasks(
        versioned=True,
        topic=topic,
        readiness_level=readiness_level,
        sort=sort,
        q=q,
        min_rating=min_rating,
        max_rating=max_rating,
        page=page,
        page_size=page_size,
        db=db,
    )
