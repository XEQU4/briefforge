"""Run the five synthetic draft-to-card examples against the local ML service."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:8001"
DEMO_FILE = Path(__file__).with_name("demo_drafts.json")


def post_json(path: str, body: dict) -> tuple[object, dict[str, str]]:
    request = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=45) as response:
        headers = {name.casefold(): value for name, value in response.headers.items()}
        return json.loads(response.read().decode("utf-8")), headers


def main() -> int:
    demos = json.loads(DEMO_FILE.read_text(encoding="utf-8"))["drafts"]
    for demo in demos:
        try:
            questions, _question_headers = post_json(
                "/generate-questions",
                {"draft_text": demo["draft_text"], "topic": demo["topic"]},
            )
            card, card_headers = post_json(
                "/form-card",
                {
                    "draft_text": demo["draft_text"],
                    "questions": questions,
                    "answers": demo["answers"],
                },
            )
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"{demo['id']}: request failed: {exc}", file=sys.stderr)
            return 1

        print(f"\n## {demo['id']} ({demo['language']}) — {demo['topic']}")
        print(f"Generation: {card_headers.get('x-generation-mode', 'unknown')}")
        if "x-generation-notice" in card_headers:
            print(f"Notice: {card_headers['x-generation-notice']}")
        print("Questions:")
        print(json.dumps(questions, ensure_ascii=False, indent=2))
        print("Task card:")
        print(json.dumps(card, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
