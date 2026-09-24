"""Backend adapter for the ML service, including deterministic outage fallbacks."""

import json
import logging
from typing import Any

import httpx

from app.core.config import ML_SERVICE_URL

logger = logging.getLogger(__name__)

NEUTRAL_TOPIC = "Topic not specified"
UPSTREAM_CARD_FIELDS = (
    "context",
    "need",
    "users",
    "data_materials",
    "constraints",
    "expected_result",
    "success_criteria",
)
GENERATED_CARD_FIELDS = frozenset((*UPSTREAM_CARD_FIELDS, "title"))

_FALLBACK_QUESTIONS = {
    "What specific need or problem should this task address?": "need",
    "Who are the intended users or beneficiaries?": "users",
    "What result would show that the task is successful?": "success_criteria",
}


def _stub_questions(_: str) -> list[str]:
    return list(_FALLBACK_QUESTIONS)


def _new_ml_client(timeout: float) -> httpx.AsyncClient:
    """Separate factory so tests can mock the actual HTTP transport."""
    return httpx.AsyncClient(timeout=timeout)


def _failure_reason(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout", ""
    if isinstance(exc, httpx.HTTPStatusError):
        return "upstream_http_error", f" status={exc.response.status_code}"
    if isinstance(exc, httpx.ConnectError):
        return "connection_error", ""
    if isinstance(exc, httpx.RequestError):
        return "connection_error", ""
    if isinstance(exc, (json.JSONDecodeError, ValueError, TypeError)):
        return "invalid_response", ""
    return "invalid_response", ""


def _log_failure(operation: str, reason: str, suffix: str = "") -> None:
    logger.warning("ML %s fallback reason=%s%s", operation, reason, suffix)


def _log_exception(operation: str, exc: Exception) -> None:
    reason, suffix = _failure_reason(exc)
    _log_failure(operation, reason, suffix)


def _valid_question_list(questions: Any) -> bool:
    return (
        isinstance(questions, list)
        and len(questions) >= 3
        and all(isinstance(question, str) and 0 < len(question.strip()) <= 2_000 for question in questions)
        and len({question.strip() for question in questions}) == len(questions)
    )


async def get_clarifying_questions(draft_text: str, topic: str | None) -> list[str]:
    if len(draft_text) > 30_000:
        _log_failure("generate_questions", "upstream_input_incompatible")
        return _stub_questions(draft_text)
    upstream_topic = topic if topic and topic.strip() else NEUTRAL_TOPIC
    if len(upstream_topic) > 500:
        _log_failure("generate_questions", "upstream_input_incompatible")
        return _stub_questions(draft_text)

    try:
        async with _new_ml_client(timeout=8.0) as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/generate-questions",
                json={"draft_text": draft_text, "topic": upstream_topic},
            )
            response.raise_for_status()
            data = response.json()
        questions = data.get("questions", data) if isinstance(data, dict) else data
        if _valid_question_list(questions):
            return [question.strip() for question in questions]
        _log_failure("generate_questions", "invalid_response")
    except Exception as exc:
        _log_exception("generate_questions", exc)
    return _stub_questions(draft_text)


def _extract_card(
    draft_text: str,
    questions: list[str],
    answers: dict[str, str],
) -> dict[str, Any]:
    """Fallback only maps the backend's exact fixed questions; other answers stay unmapped."""
    text = draft_text.strip()
    card: dict[str, Any] = {field: None for field in UPSTREAM_CARD_FIELDS}
    card["context"] = text or None
    for question in questions:
        field = _FALLBACK_QUESTIONS.get(question)
        answer = answers.get(question)
        if field and answer and answer.strip():
            card[field] = answer.strip()
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), None)
    card["title"] = first_line[:500] if first_line else None
    return card


def _compatible_form_input(draft_text: str, questions: list[str], answers: dict[str, str]) -> bool:
    return (
        len(draft_text) <= 30_000
        and all(isinstance(question, str) and len(question) <= 2_000 for question in questions)
        and all(
            isinstance(question, str)
            and isinstance(answer, str)
            and len(question) <= 2_000
            and len(answer) <= 10_000
            for question, answer in answers.items()
        )
    )


async def build_card_from_answers(
    draft_text: str,
    questions: list[str],
    answers: dict[str, str],
) -> dict[str, Any]:
    fallback = lambda: _extract_card(draft_text, questions, answers)
    if not _compatible_form_input(draft_text, questions, answers):
        _log_failure("form_card", "upstream_input_incompatible")
        return fallback()

    payload = {"draft_text": draft_text, "questions": questions, "answers": answers}
    try:
        async with _new_ml_client(timeout=12.0) as client:
            response = await client.post(f"{ML_SERVICE_URL}/form-card", json=payload)
            response.raise_for_status()
            data = response.json()
        card = data.get("card", data) if isinstance(data, dict) else None
        if not isinstance(card, dict):
            _log_failure("form_card", "invalid_response")
            return fallback()
        if not set(card).intersection(UPSTREAM_CARD_FIELDS):
            _log_failure("form_card", "invalid_response")
            return fallback()
        if any(
            field in card and card[field] is not None and not isinstance(card[field], str)
            for field in UPSTREAM_CARD_FIELDS
        ):
            _log_failure("form_card", "invalid_response")
            return fallback()
        # Ignore all fields outside the upstream's seven-field TaskCard schema.
        return {field: card[field] for field in UPSTREAM_CARD_FIELDS if field in card}
    except Exception as exc:
        _log_exception("form_card", exc)
        return fallback()
