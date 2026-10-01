# ML service

This FastAPI service generates exactly three clarifying questions and forms a task card. With a configured OpenAI key, it reads English, Russian, and Kazakh prose and selects target card fields; the service renders each field from a fixed localized template, and the public response remains a list of strings. Card values must be grounded in field-specific draft evidence or an answer for that question target; unknown fields are `null`. The AI path receives the original question-answer pairs and a target resolved from the exact public question text. No process-local state is needed, so generated question targets remain available after restarts and across workers. Draft extractions require a verbatim span plus field-specific label or prose cues; answers with unknown targets are not assigned.

## Setup

For the complete Docker installation, use the [root quick start](../README.md#quick-start).
It needs no key or env file. Optional Compose settings belong in the root `.env`,
documented by [`.env.example`](../.env.example); `ml/.env` is not copied into the
Docker image. The instructions below are for running this service separately.

From this directory, create a virtual environment and install the development dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

No key is required. To optionally enable OpenAI for a standalone service, put the key in `ml/.env` as `OPENAI_API_KEY=...`. The local `.env.example` uses the nonfunctional placeholder `PASTE_YOUR_OPENAI_API_KEY_HERE`, which selects the rule-based fallback. `ml/.env` is ignored by Git. The service reads this file relative to `service/main.py`, regardless of the current directory. Existing shell environment variables take precedence over `.env`; clear a shell `OPENAI_API_KEY` override if you want the file value to take effect. `OPENAI_MODEL` is also read there and defaults to `gpt-4o-mini`. Empty and recognized placeholder values select the fallback; any other nonempty value selects the OpenAI path, and the provider determines whether it is valid. Provider errors for a configured value return controlled HTTP errors instead of switching modes.

The service works without a configured API key using a rule-based fallback. Question selection considers labelled fields and recognizable evidence in English, Russian, and recognized Kazakh prose, then asks about missing or vague details. It prioritizes useful data, deliverables and success criteria, while asking about the core need first when it is unclear. The fallback cannot understand arbitrary prose as well as the model. Card extraction remains conservative: it recognizes explicit labels and exact service question templates; unfamiliar or edited answer questions are left unmapped. Whole-answer placeholders such as `TBD`, `not sure`, `не знаю`, `пока неизвестно`, and `уточним позже` count as unknown. A substantive answer containing one of those phrases is retained, and meaningful negatives such as “No personal data may be used” remain data. Answers in `/form-card` must be keyed by their exact question text.

## Launch

From `ml/`:

```sh
uvicorn service.main:app --reload --port 8001
```

The API is available at `http://localhost:8001`; interactive API docs are at `http://localhost:8001/docs`. Responses include `X-Generation-Mode: openai` or `X-Generation-Mode: rule-based-stub`. Stub responses also include `X-Generation-Notice`.

After changing `ml/.env`, stop the running service and launch it again with the command above so it reads the updated configuration.

## Tests

From `ml/`, run:

```sh
python -m pytest
```

The tests use a mocked provider and do not make paid API calls. A mocked AI test checks provider request/response behavior and is not evidence of live model quality. For repeatable deterministic fallback quality evaluation, run:

```sh
python evaluation/run_evaluation.py
```

The offline evaluator loads 13 synthetic cases from `evaluation/cases.json`, exercises `/generate-questions` and then `/form-card` in-process, reports exact field matches, missing expected values, and unexpectedly populated fields, and exits nonzero on failures. It clears the API key for these calls and does not contact a provider. Its results measure the rule-based fallback only.

## Backend adapter smoke

With the ML service running locally without an API key, run from `ml/`:

```sh
python scripts/backend_contract_smoke.py --base-url http://127.0.0.1:8001
```

This uses synthetic data to call the backend's real ML adapter against both endpoints and checks that question targets and card values survive the request/response boundary. It makes no provider calls.

## Question quality evaluation

The provider selects three distinct target fields without writing question wording. The service pairs each selected field with a fixed localized template. The public `/generate-questions` response remains exactly three strings, and `/form-card` recovers each target by exact template lookup. The topic is context and need not be quoted in questions. Drafts and answers remain untrusted evidence; instruction-like text does not establish a fact or override the system prompt. Card evidence validation still runs after provider extraction.

From `ml/`, run the new structural evaluation in addition to the endpoint evaluation:

```sh
python evaluation/run_question_evaluation.py
```

`evaluation/question_quality_cases.json` contains 12 synthetic weak drafts across university appointments, internships, reporting, room scheduling, logistics, documents, student feedback, accessibility, energy use and customer support. Cases include English and Russian, short and partially complete drafts, known users or data expressed in prose, vague success criteria and prompt-injection-like text. Each has human annotations for supplied fields, strong clarification candidates, expected language and factual terms that should not appear.

The report includes case counts, exactly-three counts, duplicate fields and questions, near-duplicate flags, questions about supplied fields, language mismatches, excessive length, empty questions, schema errors and forbidden-term flags. Strong-candidate matches are descriptive guidance, not a hard-coded score or a change to backend ratings. The evaluator calls only the deterministic fallback and blocks provider construction even if `ml/.env` contains a real key. It exits nonzero on reported violations or review flags.

These are **structural checks**, not proof of semantic quality. Language detection checks script, near-duplicate detection checks textual similarity, and forbidden terms flag lexical matches; none proves that a question is natural, useful or free of invented facts. A human should inspect whether each question asks for a new detail that can go directly into the card, uses only grounded context, targets one field, uses the expected localized wording, and reads naturally in its language. When fewer than three fields need clarification, check especially carefully that follow-ups seek new details instead of repeating known facts. Mocked provider tests verify safeguards and contracts; they do not measure live wording quality.

For an optional **paid** sample of 3–5 provider-generated question sets, explicitly opt in:

```sh
python scripts/live_question_quality.py --live --count 5
```

The script requires a real configured key, prints `INPUT`, actual internal `TARGET FIELDS`, and `GENERATED QUESTIONS`, and calls question generation only. Without `--live`, it makes no calls. It never prints the key or raw provider error details. This is separate from automated tests; live calls are never part of `python -m pytest` or either offline evaluator.

To save a live sample and score its structure offline:

```sh
python scripts/live_question_quality.py --live --count 5 --output /tmp/question-quality-output.json
python evaluation/run_question_evaluation.py --outputs /tmp/question-quality-output.json
```

Saved output has the shape `{"cases": [{"id": "case_id", "questions": [{"field": "data_materials", "question": "..."}, ...]}]}`. Failed attempts are retained with `"questions": null` and count as generation errors, so the report includes every attempted case. The evaluator scores matching case IDs in that file without contacting a provider. Neither the offline report nor this small live sample replaces human review of usefulness and factual grounding.

## Optional live evaluation

With the local service running and a real key configured, run from `ml/`:

```sh
python scripts/live_smoke_test.py
```

This sends the three English and Russian synthetic cases in `evaluation/live_cases.json` through both endpoints and reports question/card schema validity, generation modes, evidence checks, and expected answer mapping. It makes OpenAI requests and incurs API usage. A passing run checks only these examples; it does not prove general extraction accuracy. The script refuses to run if the key is absent or still a placeholder. It is optional and is not part of the offline test suite; no live calls were made during implementation or offline testing.

## Demo requests

Five synthetic examples with different levels of completeness are in `examples/demo_drafts.json`. With the service running, call both endpoints for all five examples with:

```sh
python examples/run_demos.py
```

The demo script sends each draft to `/generate-questions`, then submits the generated questions and its sample answers to `/form-card`. It prints each question list, card, and generation mode.

Generate questions:

```sh
curl -i http://localhost:8001/generate-questions \
  -H 'Content-Type: application/json' \
  -d '{"draft_text":"Нужен инструмент для подготовки отчетов","topic":"Отчеты"}'
```

Form a card by answering generated questions. Use each exact question string as the key for its answer:

```sh
curl -i http://localhost:8001/form-card \
  -H 'Content-Type: application/json' \
  -d '{"draft_text":"Нужен инструмент для подготовки отчетов","questions":["Кто будет пользоваться решением?"],"answers":{"Кто будет пользоваться решением?":"Финансовые аналитики"}}'
```

The card response contains exactly `context`, `need`, `users`, `data_materials`, `constraints`, `expected_result`, and `success_criteria`.

## Russian clarification example

Start with a weak draft and topic:

```json
{"draft_text":"Нужен сервис для записи к школьному психологу. Пользователи: пока неизвестно.","topic":"Запись к школьному психологу"}
```

`POST /generate-questions` asks in Russian about high-value missing details. A placeholder such as `пока неизвестно` does not establish the audience. Depending on the missing information, useful question styles include “Какие данные о записи будут доступны команде, если они есть?” and “По какому измеримому показателю вы оцените удобство записи?”. Examples are illustrative; use the exact three strings returned by the request as answer keys. For example, if these questions were returned:

```json
{
  "draft_text":"Нужен сервис для записи к школьному психологу. Пользователи: пока неизвестно.",
  "questions":["Кто будет пользоваться сервисом записи?","Какие данные о записи будут доступны команде, если они есть?","По какому измеримому показателю вы оцените удобство записи?"],
  "answers":{
    "Кто будет пользоваться сервисом записи?":"Ученики и их родители",
    "Какие данные о записи будут доступны команде, если они есть?":"Расписание специалистов в CSV",
    "По какому измеримому показателю вы оцените удобство записи?":"Ожидание записи не более трех дней"
  }
}
```

`POST /form-card` can then fill `users`, `data_materials`, and `success_criteria` with those exact answers. The placeholder in the draft does not overwrite the clarified user value; other unsupported fields remain `null`. Question wording comes from fixed localized templates for both generation modes. Always use the exact strings returned by the request; edited or third-party wording is deliberately left unmapped.
