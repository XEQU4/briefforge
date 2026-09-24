# API contract

All JSON responses use the fields shown below. `status` is one of `draft`, `clarifying`, `card_ready`, `confirmed`; proposal status is `pending`, `accepted`, or `rejected`.
`readiness_level` is one of `draft` (0–39), `working` (40–69), `ready` (70–89), or `priority` (90–100).

## Tasks

### `POST /tasks`

Request: `{ "draft_text": "string", "topic": "string|null" }`

Response `201`: `{ "task": Task, "questions": [Question] }`. The task is created in `clarifying` status and at least three questions are returned.

### `PATCH /tasks/{id}/answers`

Request: `{ "answers": ["answer"] }` or `{ "answers": { "question key": "answer" } }`

Response: `Task` with the generated editable card and `card_ready` status.

### `PATCH /tasks/{id}`

Request: any subset of card fields (`title`, `context`, `need`, `users`, `data_materials`, `constraints`, `expected_result`, `success_criteria`, `contact`, `interaction_format`, `topic`) and optionally `status`.

Response: `Task`.

### `POST /tasks/{id}/confirm`

Request: `{}`

Response: `Task` with recalculated `rating_score`, `rating_breakdown`, `readiness_level`, and `confirmed` status.

### `GET /tasks/{id}/rating`

Response: `{ "score": 0, "readiness_level": "draft", "breakdown": { "context+need": 0, "data_materials": 0, "expected_result": 0, "success_criteria": 0, "constraints": 0, "users": 0, "contact+interaction_format": 0 }, "missing_fields": ["context"], "suggestions": ["Add context"] }` (readiness is `draft`, `working`, `ready`, or `priority`; `suggestions` gives actionable guidance for each missing field.)

### `GET /tasks`

Query parameters: optional `topic`, `readiness_level`, and `sort=rating`.

Response: `[Task]` containing confirmed catalog tasks.

`Task`: `{ "id": 1, "title": "string|null", "context": "string|null", "need": "string|null", "users": "string|null", "data_materials": "string|null", "constraints": "string|null", "expected_result": "string|null", "success_criteria": "string|null", "contact": "string|null", "interaction_format": "string|null", "topic": "string|null", "status": "confirmed", "rating_score": 0, "rating_breakdown": {}, "readiness_level": "draft", "created_at": "datetime|null", "updated_at": "datetime|null" }`

`Question`: `{ "id": 1, "task_id": 1, "question_text": "string", "answer_text": "string|null", "order": 1 }`

## Proposals

### `POST /tasks/{id}/proposals`

Request: `{ "team_id": 1, "idea": "string", "plan": "string|null", "deadline": "string|null", "link": "string|null" }`

Response `201`: `Proposal` with `pending` status.

### `GET /tasks/{id}/proposals`

Response: `[Proposal]`.

### `PATCH /proposals/{id}`

Request: `{ "status": "pending|accepted|rejected" }`

Response: `Proposal`. This endpoint only changes a manually supplied status and never assigns a team automatically.

`Proposal`: `{ "id": 1, "task_id": 1, "team_id": 1, "idea": "string", "plan": "string|null", "deadline": "string|null", "link": "string|null", "status": "pending", "created_at": "datetime|null" }`

## Teams

### `POST /teams`

Request: `{ "name": "string", "interests": "string|null", "skills": "string|null", "technologies": "string|null" }`

Response `201`: `Team`.

### `GET /teams`

Response: `[Team]`.

`Team`: `{ "id": 1, "name": "string", "interests": "string|null", "skills": "string|null", "technologies": "string|null" }`
# ML service API

Base URL: `http://localhost:8001` when running the ML service locally (`cd ML && uvicorn service.main:app --reload --port 8001`). Both endpoints accept and return JSON. Unknown card fields are `null`. A `X-Generation-Mode` response header is `openai` when extraction used the configured OpenAI API and `rule-based-stub` when it did not. Stub responses also include `X-Generation-Notice` explaining that no API key is configured. The service never supplies unsupported facts: extracted card values must be present in the draft or in a submitted answer.

## `POST /generate-questions`

Request:

```json
{
  "draft_text": "We need a tool to help teams prepare monthly reports.",
  "topic": "Monthly reporting"
}
```

Response (`application/json`, a list of strings):

```json
[
  "What context should the task card include for ‘Monthly reporting’?",
  "Who will use the solution for ‘Monthly reporting’?",
  "What source data or other materials will be available for ‘Monthly reporting’?"
]
```

Questions ask only about details missing from the draft: context, users, data and materials, constraints, expected result, success criteria, and contact or interaction format. At least three questions are returned, including when most details have already been supplied. No assumptions about the task are presented as facts.

## `POST /form-card`

`questions` is a list of the question strings returned by `/generate-questions`. `answers` maps each question string to its answer; both may be empty.

Request:

```json
{
  "draft_text": "We need a tool to help teams prepare monthly reports.",
  "questions": ["Who will use the solution?"],
  "answers": {"Who will use the solution?": "Finance analysts."}
}
```

Response (`application/json`):

```json
{
  "context": null,
  "need": "We need a tool to help teams prepare monthly reports.",
  "users": "Finance analysts.",
  "data_materials": null,
  "constraints": null,
  "expected_result": null,
  "success_criteria": null
}
```

The card contains exactly these seven keys. Unanswered or unsupported details are `null`. When no `OPENAI_API_KEY` is configured, a rule-based fallback preserves the draft verbatim as `need`, fills fields only from explicitly labelled draft lines or supplied answer text, and reports the fallback in the response headers.
