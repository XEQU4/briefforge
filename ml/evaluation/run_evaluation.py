"""Run deterministic offline quality cases through both HTTP endpoints."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service import main  # noqa: E402


def evaluate() -> tuple[dict[str, object], int]:
    fixture_path = Path(__file__).with_name("cases.json")
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))["cases"]
    expected_field_names = set(main.CARD_FIELDS)
    report: dict[str, object] = {
        "evaluation_mode": "deterministic rule-based fallback; no provider calls",
        "case_count": len(cases),
        "correct_field_matches": 0,
        "expected_null_matches": 0,
        "missing_expected_values": [],
        "unexpected_populated_fields": [],
        "flow_errors": [],
    }

    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        with TestClient(main.app) as client:
            for case in cases:
                case_id = case["id"]
                generated = client.post(
                    "/generate-questions",
                    json={"draft_text": case["draft_text"], "topic": case["topic"]},
                )
                if generated.status_code != 200 or not isinstance(generated.json(), list):
                    report["flow_errors"].append(f"{case_id}: question endpoint failed")
                    continue
                questions = generated.json()
                if len(questions) < 3 or len(set(questions)) != len(questions):
                    report["flow_errors"].append(f"{case_id}: questions are not three distinct prompts")
                    continue

                answers: dict[str, str] = {}
                for field, answer in case.get("answers_by_field", {}).items():
                    matching = [q for q in questions if main._field_for_question(q) == field]
                    if not matching:
                        report["flow_errors"].append(f"{case_id}: no generated question maps to {field}")
                        continue
                    answers[matching[0]] = answer

                form_questions = list(questions)
                if case.get("extra_question"):
                    # The generated list remains intact; this also measures what
                    # deterministic fallback does with unfamiliar user wording.
                    form_questions.append(case["extra_question"])
                    answers[case["extra_question"]] = case["extra_answer"]

                formed = client.post(
                    "/form-card",
                    json={
                        "draft_text": case["draft_text"],
                        "questions": form_questions,
                        "answers": answers,
                    },
                )
                if formed.status_code != 200:
                    report["flow_errors"].append(f"{case_id}: form endpoint returned {formed.status_code}")
                    continue
                card = formed.json()
                if set(card) != expected_field_names:
                    report["flow_errors"].append(f"{case_id}: response schema changed")
                    continue

                expected = case["expected_fields"]
                expected_null = set(case["expected_null_fields"])
                if set(expected) | expected_null != expected_field_names or set(expected) & expected_null:
                    report["flow_errors"].append(f"{case_id}: fixture does not cover every card field")

                for field, value in expected.items():
                    if card[field] == value:
                        report["correct_field_matches"] += 1
                    else:
                        report["missing_expected_values"].append(
                            {"case": case_id, "field": field, "expected": value, "actual": card[field]}
                        )
                for field in expected_null:
                    if card[field] is None:
                        report["expected_null_matches"] += 1
                    else:
                        report["unexpected_populated_fields"].append(
                            {"case": case_id, "field": field, "actual": card[field]}
                        )

    failures = bool(
        report["missing_expected_values"]
        or report["unexpected_populated_fields"]
        or report["flow_errors"]
    )
    return report, int(failures)


if __name__ == "__main__":
    results, exit_code = evaluate()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)
