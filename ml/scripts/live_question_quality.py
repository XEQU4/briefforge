"""Explicitly opt in to a small paid question-only provider quality check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service import main  # noqa: E402

CASES_FILE = ROOT / "evaluation" / "question_quality_cases.json"
SAMPLE_IDS = (
    "university_appointments_en",
    "internship_matching_ru",
    "reporting_automation_en",
    "injection_like_text_en",
    "very_short_logistics_ru",
)


def main_run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow paid provider calls (required)")
    parser.add_argument("--count", type=int, choices=(3, 4, 5), default=5)
    parser.add_argument("--output", type=Path, help="Optionally save actual target fields and questions for offline scoring")
    args = parser.parse_args(argv)
    if not args.live:
        print("Live evaluation was not run. Add --live to explicitly allow paid provider calls.")
        return 2
    api_key = main._configured_api_key()
    if not api_key:
        print("Live evaluation was not run: configure OPENAI_API_KEY in ML/.env or the shell.")
        return 2
    try:
        cases_by_id = {
            case["id"]: case for case in json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
        }
        cases = [cases_by_id[case_id] for case_id in SAMPLE_IDS[:args.count]]
    except (OSError, ValueError, KeyError, TypeError):
        print("Live evaluation was not run: the question-quality fixture could not be read.")
        return 2

    print(f"Live question evaluation: {len(cases)} examples; OpenAI API usage will be incurred.")
    print("Inspect usefulness, naturalness, grounding and optional examples manually; structural checks cannot prove these.")
    records = []
    failures = 0
    for case in cases:
        print(f"\nINPUT [{case['id']}]\n{case['draft_text']}\nTOPIC: {case['topic']}")
        try:
            request = main.GenerateQuestionsRequest(draft_text=case["draft_text"], topic=case["topic"])
            generated = main._model_targeted_questions(request, api_key)
            records.append({"id": case["id"], "questions": [item.model_dump() for item in generated]})
            print("TARGET FIELDS: " + ", ".join(item.field for item in generated))
            print("GENERATED QUESTIONS:")
            for item in generated:
                print(f"- {item.question}")
        except Exception as exc:
            failures += 1
            # Keep every attempted case in saved output so offline scoring cannot
            # silently drop provider failures from the denominator.
            records.append({"id": case["id"], "questions": None})
            # Never print exception details, credentials or raw provider payloads.
            print(f"TARGET FIELDS: unavailable\nGENERATED QUESTIONS: unavailable ({type(exc).__name__}); check provider configuration or service validation.")
    if args.output:
        try:
            args.output.write_text(json.dumps({"cases": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            print("Could not save evaluation output.")
            return 1
    print(f"\nCompleted {len(records) - failures}/{len(cases)} examples. This is a human review sample, not a semantic quality score.")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main_run())
