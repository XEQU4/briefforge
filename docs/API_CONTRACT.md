# API contract

All JSON responses use the fields shown below. `TaskStatus` is one of `draft`, `clarifying`, `card_ready`, `confirmed`; `ProposalStatus` is one of `pending`, `accepted`, or `rejected`. Status values are lowercase strings.
`readiness_level` is one of `draft` (0–39), `working` (40–69), `ready` (70–89), or `priority` (90–100).

## Health

### `GET /health/live`

Returns `{ "status": "ok" }` without querying the database or external services.

### `GET /health/ready`

Runs a lightweight database query. Returns `{ "status": "ready", "database": "ok" }` when PostgreSQL is reachable, or a controlled `503` response when it is unavailable.

## Authentication

Authentication uses an opaque server-side session. The browser receives the `briefforge_session` cookie (`HttpOnly`, `SameSite=Lax`, `Path=/`, configured lifetime); PostgreSQL stores only its SHA-256 hash. The `Secure` attribute is controlled by `SESSION_COOKIE_SECURE` and must be enabled behind HTTPS in production. Responses from `/auth/*` are not cacheable. Public user responses contain only `id`, `email`, `display_name`, `created_at`, and `updated_at`.

For cookie-authenticated unsafe requests, send `X-CSRF-Token` with the value of the separate `briefforge_csrf` cookie. This CSRF cookie is `SameSite=Lax`, `Path=/`, and intentionally readable by browser code; its value is random, and only its hash is stored with the session. The server requires the header, CSRF cookie, and stored hash to match. `GET`, `HEAD`, and `OPTIONS` are exempt. This is a synchronizer-token check; CORS is not used as CSRF protection.

### `POST /auth/register`

Request: `{ "email": "person@example.com", "password": "at least 10 characters", "display_name": "Name|null" }`

Creates a user and session, sets both cookies, and returns the public user with status `201`. Email is normalized. Passwords must be 10–128 characters and not whitespace-only. Duplicate email returns `409`; request validation errors do not echo submitted password values.

Example response (`201`): `{ "id": 1, "email": "person@example.com", "display_name": "Name", "created_at": "datetime", "updated_at": "datetime" }`.

### `POST /auth/login`

Request: `{ "email": "person@example.com", "password": "..." }`

On success, creates a session, updates `last_login_at`, sets both cookies, and returns the public user. Unknown email, incorrect password, inactive user, and users without a password hash all return the same generic `401` response.

Example error (`401`): `{ "detail": "Invalid email or password" }`.

### `POST /auth/logout`

Revokes the session if one is present and clears both cookies. Repeated logout is safe. With an active session cookie, the CSRF header is required.

### `GET /auth/me`

Returns the public user for an active, non-expired session. Missing, malformed, expired, revoked, or inactive sessions return `401`.

Example error (`401`): `{ "detail": "Authentication required" }`.

`SESSION_TTL_SECONDS` defaults to seven days. Sessions do not slide. Existing users created before local-password authentication have a nullable `password_hash` and cannot log in until a password is established through a future account-recovery/password-setting flow; no password is invented during migration. Existing task/team/proposal endpoints remain unauthenticated in this phase. Object-level authorization is deferred.

## Tasks

### `POST /tasks`

Request: `{ "draft_text": "string", "topic": "string|null" }`

Response `201`: `{ "task": Task, "questions": [Question] }`. The task is created in `clarifying` status and at least three questions are returned.

### `PATCH /tasks/{id}/answers`

Request: `{ "answers": ["answer"] }` or `{ "answers": { "question key": "answer" } }`

Response: `Task` with the generated editable card and `card_ready` status.

### `PATCH /tasks/{id}`

Request: any subset of editable card fields (`title`, `context`, `need`, `users`, `data_materials`, `constraints`, `expected_result`, `success_criteria`, `contact`, `interaction_format`, `topic`). Task status cannot be changed through this endpoint.

Response: `Task`.

### `POST /tasks/{id}/confirm`

Request: `{}`

Response: `Task` with recalculated `rating_score`, `rating_breakdown`, `readiness_level`, and `confirmed` status.

Task lifecycle transitions are `draft` → `clarifying` → `card_ready` → `confirmed`. Task creation continues to start at `clarifying`; confirmation requires `card_ready`. Reconfirming an already confirmed task is idempotent.

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

Proposal lifecycle transitions are `pending` → `accepted` or `pending` → `rejected`. Repeating `pending` is idempotent; `accepted` and `rejected` are terminal.

`Proposal`: `{ "id": 1, "task_id": 1, "team_id": 1, "idea": "string", "plan": "string|null", "deadline": "string|null", "link": "string|null", "status": "pending", "created_at": "datetime|null" }`

## Teams

### `POST /teams`

Request: `{ "name": "string", "interests": "string|null", "skills": "string|null", "technologies": "string|null" }`

Response `201`: `Team`.

### `GET /teams`

Response: `[Team]`.

`Team`: `{ "id": 1, "name": "string", "interests": "string|null", "skills": "string|null", "technologies": "string|null" }`
# ML service API

Base URL: `http://localhost:8001` when running the ML service locally (`cd ml && uvicorn service.main:app --reload --port 8001`). Both endpoints accept and return JSON. Unknown card fields are `null`. A `X-Generation-Mode` response header is `openai` when extraction used the configured OpenAI API and `rule-based-stub` when it did not. Stub responses also include `X-Generation-Notice` explaining that no API key is configured. The service never supplies unsupported facts: extracted card values must be present in the draft or in a submitted answer.

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
