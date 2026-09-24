"""Optional paid live evaluation for the configured local OpenAI-backed service."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

ML_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_ROOT))

from service import main  # noqa: E402


BASE_URL = "http://127.0.0.1:8001"
CASES_FILE = ML_ROOT / "evaluation" / "live_cases.json"


def post_json(path: str, payload: dict[str, Any]) -> tuple[Any, str]:
    request = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        return (
            json.loads(response.read().decode("utf-8")),
            response.headers.get("X-Generation-Mode", "missing"),
        )


def evaluate_case(client_case: dict[str, Any]) -> dict[str, Any]:
    questions, question_mode = post_json(
        "/generate-questions",
        {"draft_text": client_case["draft_text"], "topic": client_case["topic"]},
    )
    questions_valid = (
        isinstance(questions, list)
        and len(questions) == 3
        and all(isinstance(question, str) and question.strip() for question in questions)
        and len({question.strip() for question in questions}) == 3
    )
    if not questions_valid:
        return {
            "id": client_case["id"],
            "question_schema_valid": False,
            "generation_modes": {"generate_questions": question_mode},
        }

    answers: dict[str, str] = {}
    missing_targets = []
    for field, answer in client_case["answers_by_field"].items():
        matching = [question for question in questions if main._field_for_question(question) == field]
        if matching:
            answers[matching[0]] = answer
        else:
            missing_targets.append(field)

    card, card_mode = post_json(
        "/form-card",
        {
            "draft_text": client_case["draft_text"],
            "questions": questions,
            "answers": answers,
        },
    )
    schema_valid = (
        isinstance(card, dict)
        and set(card) == set(main.CARD_FIELDS)
        and all(value is None or isinstance(value, str) for value in card.values())
    )
    evidence = [client_case["draft_text"], *answers.values()]
    evidence_check = schema_valid and all(
        value is None or any(value in source for source in evidence)
        for value in card.values()
    )
    field_matches = {
        field: schema_valid and card[field] == answer
        for field, answer in client_case["answers_by_field"].items()
        if field in main.CARD_FIELDS
    }
    return {
        "id": client_case["id"],
        "question_schema_valid": questions_valid,
        "card_schema_valid": schema_valid,
        "generation_modes": {
            "generate_questions": question_mode,
            "form_card": card_mode,
        },
        "evidence_check": evidence_check,
        "expected_field_matches": field_matches,
        "unmatched_question_targets": missing_targets,
    }


def main_run() -> int:
    if not main._configured_api_key():
        print(json.dumps({"error": "A configured OpenAI key is required; live evaluation not run."}))
        return 2

    try:
        cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
        results = [evaluate_case(case) for case in cases]
    except (URLError, TimeoutError, ValueError, OSError, KeyError, TypeError):
        print(json.dumps({"error": "Live evaluation could not complete; check service availability and configuration."}))
        return 1

    report = {
        "evaluation_mode": "live OpenAI requests; API usage incurred",
        "case_count": len(results),
        "cases": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    passed = all(
        case.get("question_schema_valid")
        and case.get("card_schema_valid")
        and case.get("evidence_check")
        and not case.get("unmatched_question_targets")
        and all(case.get("expected_field_matches", {}).values())
        for case in results
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main_run())
