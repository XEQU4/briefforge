"""Fixed offline demo fixture creation, isolated from HTTP routing and ML."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal, commit_or_rollback
from app.models import ClarifyingQuestion, DemoSeedManifest, Proposal, Task, Team
from app.services.rating import calculate_rating, readiness_for_score

DATASET_ID = "demo-v1"
VERSION = "1"
CREATED_COUNTS = {"tasks": 13, "confirmed_tasks": 8, "drafts": 5, "teams": 5, "proposals": 10}


async def current_counts(db: AsyncSession) -> dict:
    tasks = int((await db.scalar(select(func.count()).select_from(Task))) or 0)
    confirmed = int((await db.scalar(select(func.count()).select_from(Task).where(Task.status == "confirmed"))) or 0)
    drafts = int((await db.scalar(select(func.count()).select_from(Task).where(Task.status != "confirmed"))) or 0)
    teams = int((await db.scalar(select(func.count()).select_from(Team))) or 0)
    proposals = int((await db.scalar(select(func.count()).select_from(Proposal))) or 0)
    return {"tasks": tasks, "confirmed_tasks": confirmed, "drafts": drafts, "teams": teams, "proposals": proposals}


async def seed_dataset(db: AsyncSession) -> tuple[str, dict]:
    """Return (created|already_seeded, counts); concurrent races are controlled."""
    existing = await db.scalar(select(DemoSeedManifest.id).where(DemoSeedManifest.dataset_key == DATASET_ID))
    if existing is not None:
        return "already_seeded", await current_counts(db)
    try:
        manifest = DemoSeedManifest(dataset_key=DATASET_ID, version=VERSION, created_ids={})
        db.add(manifest)
        await db.flush()  # The database uniqueness constraint serializes seed attempts.
        drafts, questions = _drafts()
        cards = _cards()
        db.add_all(drafts + cards)
        await db.flush()
        for task, question_set in zip(drafts, questions):
            task.questions.extend(ClarifyingQuestion(question_text=value, order=index)
                                  for index, value in enumerate(question_set, 1))
        teams = _teams()
        db.add_all(teams)
        await db.flush()
        proposals = _proposals(cards, teams)
        db.add_all(proposals)
        await db.flush()
        manifest.created_ids = {
            "tasks": [task.id for task in drafts + cards],
            "questions": [question.id for task in drafts for question in task.questions],
            "teams": [team.id for team in teams],
            "proposals": [proposal.id for proposal in proposals],
        }
        await commit_or_rollback(db)
        return "created", await current_counts(db)
    except (IntegrityError, OperationalError):
        await db.rollback()
        async with SessionLocal() as check:
            existing = await check.scalar(select(DemoSeedManifest.id).where(DemoSeedManifest.dataset_key == DATASET_ID))
            if existing is not None:
                return "already_seeded", await current_counts(check)
        return "conflict", {}
    except Exception:
        await db.rollback()
        raise


def _drafts():
    topics = ["Образование", "Энергетика", "Здравоохранение", "Логистика", "Образование"]
    descriptions = [
        "Нужен помощник для координаторов учебной программы.",
        "Небольшой пилот для планирования энергопотребления корпуса в часы пик.",
        "Вымышленная клиника хочет упростить запись на профилактические осмотры и напоминания пациентам.",
        "Складская команда вручную сводит ежедневные сведения о поставках из нескольких таблиц.",
        "Учебный центр ищет способ быстрее собирать обратную связь после коротких курсов и видеть темы, требующие дополнительного объяснения.",
    ]
    question_sets = [
        ["Какая ситуация сейчас?", "Кто будет пользоваться решением?", "Какой результат нужен?"],
        ["Какие данные доступны?", "Какие ограничения важны?", "Как проверить успех?"],
        ["Кто целевые пользователи?", "Как проходит текущий процесс?", "Как представить результат?"],
        ["Какие материалы можно предоставить?", "Какой срок актуален?", "Кто контакт со стороны бизнеса?"],
        ["Какую проблему нужно решить?", "С кем команде взаимодействовать?", "Что будет считаться успехом?"],
    ]
    return [Task(title=f"Черновик: демо-задача {i}", context=description, topic=topics[i - 1],
                 status="clarifying", questions=[])
            for i, description in enumerate(descriptions, 1)], question_sets


def _cards():
    topics = ["Образование", "Энергетика", "Здравоохранение", "Логистика", "Финансы", "Образование", "Энергетика", "Логистика"]
    # Missing fields are deliberate and produce scores 20, 55, 70, 80, 90, 90, 100, 100.
    coverage = [1, 3, 4, 5, 6, 6, 7, 8]
    result = []
    for i, (topic, keep_count) in enumerate(zip(topics, coverage), 1):
        values = {
            "title": f"Демо-задача {i}: анализ процесса в теме {topic}",
            "context": "Вымышленная организация хочет улучшить внутренний процесс.",
            "need": "Нужно сократить ручную работу и сделать процесс понятнее.",
            "data_materials": "Пример синтетической таблицы без персональных данных.",
            "expected_result": "Интерактивный прототип и краткое описание.",
            "success_criteria": "Команда демонстрирует рабочий сценарий на примере.",
            "constraints": "Без доступа к реальным персональным данным.",
            "users": "Сотрудники вымышленной организации.",
            "contact": f"demo-contact-{i}@example.com",
            "interaction_format": "Еженедельная онлайн-встреча",
            "topic": topic,
        }
        optional = ("context", "data_materials", "expected_result", "success_criteria", "constraints", "users", "contact")
        for index, field in enumerate(optional):
            if index >= keep_count:
                values[field] = None
        task = Task(**values, status="confirmed")
        task.rating_score, task.rating_breakdown, _ = calculate_rating(task)
        task.readiness_level = readiness_for_score(task.rating_score)
        result.append(task)
    return result


def _teams():
    return [Team(name=name, interests=interest, skills=skills, technologies=tech) for name, interest, skills, tech in [
        ("Команда Орбита", "Образование", "аналитика, UX", "Python, React"),
        ("Команда Сигнал", "Энергетика", "данные, прототипирование", "Python, SQL"),
        ("Команда Маяк", "Здравоохранение", "дизайн, исследования", "Figma, React"),
        ("Команда Поток", "Логистика", "оптимизация, карты", "Python, GIS"),
        ("Команда Искра", "Финансы", "ML, аналитика", "Python, pandas"),
    ]]


def _proposals(cards, teams):
    return [Proposal(task=cards[index % 8], team=teams[index % 5],
                     idea=f"Предложение команды {teams[index % 5].name}: прототип сценария {index + 1}.",
                     plan="Исследование, прототипирование, проверка на синтетическом примере",
                     deadline="3 недели", link=f"https://example.com/demo-prototype-{index + 1}", status="pending")
            for index in range(10)]
