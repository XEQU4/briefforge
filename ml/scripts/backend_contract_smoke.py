"""Exercise the backend ML adapter against a local, no-key ML service."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import ai_client  # noqa: E402
from service import main as ml_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    draft = "A small clinic wants to reduce missed appointments."
    topic = "Clinic appointment reminders"

    health = httpx.get(f"{base_url}/health", timeout=3.0)
    health.raise_for_status()
    probe = httpx.post(
        f"{base_url}/generate-questions",
        json={"draft_text": draft, "topic": topic},
        timeout=5.0,
    )
    probe.raise_for_status()
    if probe.headers.get("X-Generation-Mode") != "rule-based-stub":
        raise RuntimeError("Smoke check requires the ML service's no-key fallback mode.")

    ai_client.ML_SERVICE_URL = base_url
    questions = asyncio.run(ai_client.get_clarifying_questions(draft, topic))
    if len(questions) != 3 or len(set(questions)) != 3:
        raise AssertionError("Backend adapter did not accept three distinct question strings.")
    fields = [ml_service._field_for_question(question) for question in questions]
    if any(field not in ml_service.CARD_FIELDS for field in fields) or len(set(fields)) != 3:
        raise AssertionError("No-key ML questions did not retain three distinct card targets.")

    answers = {
        question: f"Synthetic answer for {field}."
        for question, field in zip(questions, fields)
    }
    card = asyncio.run(ai_client.build_card_from_answers(draft, questions, answers))
    if set(card) != set(ai_client.UPSTREAM_CARD_FIELDS):
        raise AssertionError("Backend adapter returned an unexpected card field set.")
    for question, field in zip(questions, fields):
        if card.get(field) != answers[question]:
            raise AssertionError(f"Backend adapter did not preserve the answer targeted at {field}.")

    print(json.dumps({
        "result": "passed",
        "generation_mode": probe.headers["X-Generation-Mode"],
        "question_count": len(questions),
        "target_fields": fields,
        "card_fields": sorted(card),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
