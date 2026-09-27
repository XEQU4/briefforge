"""Offline structural checks; these metrics do not measure semantic usefulness."""

from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service import main  # noqa: E402

CASES_FILE = Path(__file__).with_name("question_quality_cases.json")
VIOLATION_KEYS = (
    "question_count_violations",
    "duplicate_field_violations",
    "duplicate_question_violations",
    "near_duplicate_question_flags",
    "already_supplied_field_violations",
    "language_mismatches",
    "excessive_question_lengths",
    "empty_questions",
    "schema_violations",
    "forbidden_term_flags",
    "generation_errors",
)


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def _language_matches(question: str, expected: str) -> bool:
    # Script and vocabulary cues permit multilingual review but cannot judge
    # idiomatic wording or reliably distinguish every Cyrillic language.
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", question))
    latin = len(re.findall(r"[A-Za-z]", question))
    kazakh_letters = len(re.findall(r"[ӘәҒғҚқҢңӨөҰұҮүҺһІі]", question))
    if expected == "ru":
        return cyrillic >= 3 and cyrillic >= latin * 0.5
    if expected == "kk":
        normalized = question.casefold()
        return cyrillic >= 3 and (kazakh_letters > 0 or any(
            marker in normalized for marker in main.KAZAKH_WORD_MARKERS
        ))
    return latin >= 3 and cyrillic < latin * 0.5


def score_case(case: dict, questions: object) -> dict:
    result = {
        "id": case["id"],
        "exactly_three_questions": isinstance(questions, list) and len(questions) == 3,
        "target_fields": [],
        "strong_candidate_hits": [],
        **{key: [] for key in VIOLATION_KEYS},
    }
    if not isinstance(questions, list):
        result["schema_violations"].append("Expected an array of targeted questions")
        result["question_count_violations"].append("Expected exactly three questions")
        return result
    if len(questions) != 3:
        result["question_count_violations"].append(f"Expected 3 questions, received {len(questions)}")

    fields = []
    texts = []
    supplied = set(case.get("supplied_fields", case.get("do_not_ask", [])))
    for index, item in enumerate(questions):
        if not isinstance(item, dict) or set(item) != {"field", "question"}:
            result["schema_violations"].append({"index": index, "reason": "Expected exactly field and question keys"})
            continue
        field, question = item["field"], item["question"]
        if not isinstance(field, str) or field not in main.CARD_FIELDS:
            result["schema_violations"].append({"index": index, "reason": "Unsupported target field"})
        else:
            fields.append(field)
            if field in supplied:
                result["already_supplied_field_violations"].append({"index": index, "field": field})
        if not isinstance(question, str):
            result["schema_violations"].append({"index": index, "reason": "Question must be a string"})
            continue
        normalized = _normalize(question)
        if not normalized:
            result["empty_questions"].append(index)
        texts.append((index, normalized))
        words = len(re.findall(r"\S+", question))
        if words > main.MAX_QUESTION_WORDS or len(question) > main.MAX_QUESTION_CHARS:
            result["excessive_question_lengths"].append({"index": index, "words": words, "characters": len(question)})
        if question.strip() and not _language_matches(question, case["expected_language"]):
            result["language_mismatches"].append(index)
        for term in case.get("forbidden_factual_terms", []):
            if _normalize(term) in normalized:
                result["forbidden_term_flags"].append({"index": index, "term": term})

    result["target_fields"] = fields
    result["duplicate_field_violations"] = [field for field, count in Counter(fields).items() if count > 1]
    for offset, (index, normalized) in enumerate(texts):
        for other_index, other in texts[offset + 1:]:
            if normalized == other:
                result["duplicate_question_violations"].append([index, other_index])
            elif SequenceMatcher(None, normalized, other).ratio() >= 0.9:
                result["near_duplicate_question_flags"].append([index, other_index])
    result["strong_candidate_hits"] = sorted(set(fields) & set(case.get("strong_candidates", [])))
    return result


def evaluate(cases_file: Path = CASES_FILE, outputs_file: Path | None = None) -> tuple[dict, int]:
    cases = json.loads(cases_file.read_text(encoding="utf-8"))["cases"]
    stored = None
    input_errors = [] if cases else ["Evaluation dataset has no cases"]
    if outputs_file is not None:
        records = json.loads(outputs_file.read_text(encoding="utf-8"))["cases"]
        stored = {}
        for record in records:
            case_id = record["id"]
            if case_id in stored:
                input_errors.append(f"Duplicate saved case ID: {case_id}")
            stored[case_id] = record.get("questions")
        unknown = set(stored) - {case["id"] for case in cases}
        input_errors.extend(f"Unknown saved case ID: {case_id}" for case_id in sorted(unknown))
        # Saved outputs may intentionally cover a 3–5-case live sample only.
        cases = [case for case in cases if case["id"] in stored]
        if not cases:
            input_errors.append("No saved output IDs match evaluation cases")

    results = []
    # Patch both the key and client constructor: loading ML/.env never enables a
    # paid call here, and accidental provider use becomes an evaluation failure.
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch.object(
        main, "OpenAI", side_effect=AssertionError("Provider calls are forbidden in offline evaluation")
    ):
        for case in cases:
            try:
                questions = stored[case["id"]] if stored is not None else [
                    item.model_dump() for item in main._make_targeted_questions(case["draft_text"], case["topic"])
                ]
                result = score_case(case, questions)
                if stored is not None and questions is None:
                    result["generation_errors"].append("No saved question output for attempted case")
            except Exception as exc:
                # Print only the exception class; provider/library messages can
                # contain request contents or credentials.
                result = score_case(case, None)
                result["generation_errors"].append(type(exc).__name__)
            results.append(result)

    counts = {key: sum(len(result[key]) for result in results) for key in VIOLATION_KEYS}
    counts["schema_violations"] += len(input_errors)
    report = {
        "evaluation_mode": "saved targeted outputs; no provider calls" if stored is not None else "deterministic fallback; no provider calls",
        "case_count": len(results),
        "exactly_three_questions": sum(result["exactly_three_questions"] for result in results),
        **counts,
        "input_schema_errors": input_errors,
        "limits": {"maximum_words": main.MAX_QUESTION_WORDS, "maximum_characters": main.MAX_QUESTION_CHARS},
        "interpretation": "Structural checks only. Script, similarity and forbidden-term checks are heuristic review flags. Human review must judge usefulness, naturalness, field focus, factual grounding and whether examples are optional. Strong candidate hits are descriptive, not a quality score. Supplied-field followups need review when fewer than three fields are missing.",
        "cases": results,
    }
    return report, int(any(counts.values()))


def main_run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    parser.add_argument("--outputs", type=Path, help="Score saved {cases: [{id, questions: [{field, question}]}]} JSON without a provider")
    args = parser.parse_args(argv)
    try:
        report, exit_code = evaluate(args.cases, args.outputs)
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"error": "Evaluation files must contain valid case/output JSON; no provider calls were made."}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main_run())
