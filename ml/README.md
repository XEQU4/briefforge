# ML service

This FastAPI service generates exactly three clarifying questions and forms a task card. With a configured OpenAI key, it reads ordinary English or Russian prose and returns validated questions internally paired with their target card fields; the public response remains a list of strings. Card values must be grounded in the draft or submitted answers; unknown fields are `null`. The AI path receives the original question-answer pairs so it can interpret generated or unfamiliar wording. Its text check confirms a returned value appears in submitted evidence, but that check alone cannot prove the value was assigned to the semantically correct field.

## Setup

From this directory, create a virtual environment and install the development dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Put the OpenAI key in `ML/.env` as `OPENAI_API_KEY=...`; this is the only file you need to edit. The local `.env.example` uses the nonfunctional placeholder `PASTE_YOUR_OPENAI_API_KEY_HERE`, which selects the rule-based fallback. `ML/.env` is ignored by Git. The service reads `.env` relative to `service/main.py`, regardless of the current directory. Existing shell environment variables take precedence over `.env`; clear a shell `OPENAI_API_KEY` override if you want the file value to take effect. `OPENAI_MODEL` is also read there and defaults to `gpt-4o-mini`. Empty and recognized placeholder values select the fallback; any other nonempty value selects the OpenAI path, and the provider determines whether it is valid. Provider errors for a configured value return controlled HTTP errors instead of switching modes.

The service works without a configured API key using its labelled rule-based fallback. That fallback recognizes explicitly labelled fields, the service's generated question templates, and unambiguous question wording; unfamiliar or ambiguous answer questions are left unmapped. It returns exactly three distinct questions, prioritizing labelled fields that are missing or contain placeholders. Whole-answer placeholders such as `TBD`, `not sure`, `не знаю`, `пока неизвестно`, and `уточним позже` count as unknown. This is deliberately conservative: a substantive answer containing one of those phrases is retained, and meaningful negatives such as “No personal data may be used” remain data. Answers in `/form-card` must be keyed by their exact question text.

## Launch

From `ML/`:

```sh
uvicorn service.main:app --reload --port 8001
```

The API is available at `http://localhost:8001`; interactive API docs are at `http://localhost:8001/docs`. Responses include `X-Generation-Mode: openai` or `X-Generation-Mode: rule-based-stub`. Stub responses also include `X-Generation-Notice`.

After changing `ML/.env`, stop the running service and launch it again with the command above so it reads the updated configuration.

## Tests

From `ML/`, run:

```sh
python -m pytest
```

The tests use a mocked provider and do not make paid API calls. A mocked AI test checks provider request/response behavior and is not evidence of live model quality. For repeatable deterministic fallback quality evaluation, run:

```sh
python evaluation/run_evaluation.py
```

The offline evaluator loads 13 synthetic cases from `evaluation/cases.json`, exercises `/generate-questions` and then `/form-card` in-process, reports exact field matches, missing expected values, and unexpectedly populated fields, and exits nonzero on failures. It clears the API key for these calls and does not contact a provider. Its results measure the rule-based fallback only.

## Optional live evaluation

With the local service running and a real key configured, run from `ML/`:

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

With the no-key fallback, `POST /generate-questions` asks in Russian about missing details, including users because `пока неизвестно` is a placeholder. It returns three prompts such as `Кто будет пользоваться решением для темы «Запись к школьному психологу»?`, `Какие данные или материалы и в каких форматах будут доступны для темы «Запись к школьному психологу»?`, and `Как вы будете оценивать успешность результата по измеримым показателям или целевому значению для темы «Запись к школьному психологу»?`. Submit the exact returned strings as keys and only include facts the user supplied:

```json
{
  "draft_text":"Нужен сервис для записи к школьному психологу. Пользователи: пока неизвестно.",
  "questions":["Кто будет пользоваться решением для темы «Запись к школьному психологу»?","Какие данные или материалы и в каких форматах будут доступны для темы «Запись к школьному психологу»?","Как вы будете оценивать успешность результата по измеримым показателям или целевому значению для темы «Запись к школьному психологу»?"],
  "answers":{
    "Кто будет пользоваться решением для темы «Запись к школьному психологу»?":"Ученики и их родители",
    "Какие данные или материалы и в каких форматах будут доступны для темы «Запись к школьному психологу»?":"Расписание специалистов в CSV",
    "Как вы будете оценивать успешность результата по измеримым показателям или целевому значению для темы «Запись к школьному психологу»?":"Ожидание записи не более трех дней"
  }
}
```

`POST /form-card` can then fill `users`, `data_materials`, and `success_criteria` with those exact answers. The placeholder in the draft does not overwrite the clarified user value; other unsupported fields remain `null`. With a real key, question wording is generated dynamically, so always use the exact strings returned by that request.
