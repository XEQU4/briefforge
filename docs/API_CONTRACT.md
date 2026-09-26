# API contract

All JSON responses use the fields shown below. `TaskStatus` is one of `draft`, `clarifying`, `card_ready`, `confirmed`; `ProposalStatus` is one of `pending`, `accepted`, or `rejected`. Status values are lowercase strings.
`readiness_level` is one of `draft` (0–39), `working` (40–69), `ready` (70–89), or `priority` (90–100).

## Versioning and pagination

`/api/v1` is the preferred product API namespace. Current unversioned product routes remain temporary compatibility aliases to the same handlers and authorization rules; they may be removed in a later release. Health routes (`/health/live` and `/health/ready`) remain unversioned.

Versioned task, team, and task-proposal list endpoints return `{ "items": [], "page": 1, "page_size": 20, "total": 0, "pages": 0 }`. `page` defaults to `1` and must be at least `1`. `page_size` defaults to `20` and must be between `1` and `100`. Counts are calculated in the database. Empty results have `pages: 0`. The corresponding unversioned list routes keep their existing array response.

Versioned and unversioned examples below use the current compatibility paths; prepend `/api/v1` to use the preferred API. For example, use `GET /api/v1/tasks` for the paginated catalog and `GET /tasks` for its legacy array response.

## Health

### `GET /health/live`

Returns `{ "status": "ok" }` without querying the database or external services.

### `GET /health/ready`

Runs a lightweight database query. Returns `{ "status": "ready", "database": "ok" }` when PostgreSQL is reachable, or a controlled `503` response when it is unavailable.

## Authentication

Authentication uses an opaque server-side session. The browser receives the `briefforge_session` cookie (`HttpOnly`, `SameSite=Lax`, `Path=/`, configured lifetime); PostgreSQL stores only its SHA-256 hash. The `Secure` attribute is controlled by `SESSION_COOKIE_SECURE` and must be enabled behind HTTPS in production. Responses from `/auth/*` and `/api/v1/auth/*` are not cacheable. Public user responses contain only `id`, `email`, `display_name`, `created_at`, and `updated_at`.

For cookie-authenticated unsafe requests, send `X-CSRF-Token` with the value of the separate `briefforge_csrf` cookie. This CSRF cookie is `SameSite=Lax`, `Path=/`, and intentionally readable by browser code; its value is random, and only its hash is stored with the session. The server requires the header, CSRF cookie, and stored hash to match. `GET`, `HEAD`, and `OPTIONS` are exempt. This is a synchronizer-token check; CORS is not used as CSRF protection.

### `POST /auth/register` (also `POST /api/v1/auth/register`)

Request: `{ "email": "person@example.com", "password": "at least 10 characters", "display_name": "Name|null" }`

Creates a user and session, sets both cookies, and returns the public user with status `201`. Email is normalized. Passwords must be 10–128 characters and not whitespace-only. Duplicate email returns `409`; request validation errors do not echo submitted password values.

Example response (`201`): `{ "id": 1, "email": "person@example.com", "display_name": "Name", "created_at": "datetime", "updated_at": "datetime" }`.

### `POST /auth/login` (also `POST /api/v1/auth/login`)

Request: `{ "email": "person@example.com", "password": "..." }`

On success, creates a session, updates `last_login_at`, sets both cookies, and returns the public user. Unknown email, incorrect password, inactive user, and users without a password hash all return the same generic `401` response.

Example error (`401`): `{ "detail": "Invalid email or password" }`.

### `POST /auth/logout` (also `POST /api/v1/auth/logout`)

Revokes the session if one is present and clears both cookies. Repeated logout is safe. With an active session cookie, the CSRF header is required.

### `GET /auth/me` (also `GET /api/v1/auth/me`)

Returns the public user for an active, non-expired session. Missing, malformed, expired, revoked, or inactive sessions return `401`.

Example error (`401`): `{ "detail": "Authentication required" }`.

`SESSION_TTL_SECONDS` defaults to seven days. Sessions do not slide. Existing users created before local-password authentication have a nullable `password_hash` and cannot log in until a password is established through a future account-recovery/password-setting flow; no password is invented during migration.

Both organization roles (`owner` and `member`) may manage organization tasks. Both team roles (`owner` and `member`) may submit proposals for their team. Creator, team-owner, and proposal-submitter identities are derived from the current session. The backend does not accept frontend role switches.

Cookie-authenticated `POST`, `PATCH`, `PUT`, and `DELETE` requests require the CSRF header above. Public `GET` endpoints are exempt.

## Organizations

### `GET /organizations/{id}` — authenticated organization member

Also available as `GET /api/v1/organizations/{id}`. Returns `OrganizationRead` without membership data. A non-member receives `403`; a missing organization receives `404`.

### `POST /organizations` — authenticated

Request: `{ "name": "Example Business", "slug": "example-business" }`

Creates the organization and an `owner` membership for the current user atomically. Returns `OrganizationRead` with status `201`. A duplicate normalized slug returns `409`.

### `GET /organizations/mine` — authenticated

Returns the current user's organizations as `[OrganizationRead]`; organizations without a membership are omitted.

### `GET /api/v1/organizations/{id}/tasks` — authenticated organization member

Returns the selected organization's tasks as the standard pagination envelope
of `TaskRead`. The caller must belong to the organization; a non-member receives
`403`, and a missing organization receives `404`. Results are scoped to that
organization and include private workflow states, including `clarifying`,
`card_ready`, `confirmed`, unpublished, published, and archived tasks. This
private list does not change the public catalog.

Supports `q` (case-insensitive search over title, context, need, and topic),
`status` (`TaskStatus`), `publication_status` (`TaskPublicationStatus`),
`page`, `page_size`, and `sort` (`newest`, `oldest`, or `rating`; defaults to
`newest`). Filtering, counting, ordering, and page limits run in the database;
equal sort values use a stable task ID tie-breaker.

## Tasks

### Content workflow and publication

`status` describes content preparation (`draft`, `clarifying`, `card_ready`,
`confirmed`). The separate `publication_status` describes visibility:
`unpublished`, `published`, or `archived`. New tasks default to `unpublished`;
only `confirmed` + `published` tasks are public. Publication state is
server-controlled and cannot be set through task creation or generic `PATCH`.

For compatibility, the first successful confirmation of a `card_ready`,
unpublished task confirms and publishes it in one operation. Reconfirming an
already confirmed task recalculates its rating while preserving its current
publication state. A non-confirmed archived task must first be restored with
unpublish; invalid content workflow transitions remain `409`.

| Action | Allowed starting state | Result |
| --- | --- | --- |
| First confirm | `card_ready` + `unpublished` | `confirmed` + `published` |
| Reconfirm | `confirmed` + any publication state | `confirmed` + same publication state |
| Publish | `confirmed` + `unpublished` or `archived` | `confirmed` + `published` |
| Unpublish | any publication state | same content state + `unpublished` |
| Archive | any content state and publication state | same content state + `archived` |

Authenticated organization members can call `POST /api/v1/tasks/{id}/publish`,
`POST /api/v1/tasks/{id}/unpublish`, and `POST /api/v1/tasks/{id}/archive`;
matching unversioned aliases remain available during the compatibility period.
Each returns `TaskRead` with `200`; repeated no-op actions preserve the row
without an unnecessary write. The existing CSRF header is required for these
cookie-authenticated requests.

Public task catalog, count, filtering, search, detail, and rating reads include
only tasks that are both `confirmed` and `published`. An authenticated member
of the owning organization may read other task states privately; unrelated
users receive `403`, anonymous private reads receive `401`, and ownerless
private legacy tasks remain inaccessible. Access-controlled task responses
are not publicly cached. Editing or answering a task never changes its
publication state.

New proposals require a confirmed, published task and an authenticated member
of the selected team. Unpublished, archived, and non-confirmed tasks return
`409` to otherwise authorized team members. Unpublishing or archiving does not
delete or change existing proposals; organization members retain access to
list and decide them.

Migration backfills existing confirmed tasks as published and all other tasks
as unpublished. Rolling this feature back to the old application can expose
previously hidden confirmed tasks because that application has no publication
visibility filter; rollback is not a harmless reset.

### `GET /tasks/{id}`

Also available as `GET /api/v1/tasks/{id}`. Confirmed and published tasks are public. Other task states require authentication and organization membership; an ownerless private legacy task is inaccessible through this route. Returns `TaskRead`, including `publication_status`; missing tasks return `404`.

### `GET /api/v1/tasks/{id}/questions` — authenticated organization member

Returns `[QuestionRead]` for a task only when the caller belongs to its
organization. Questions are ordered by `order` ascending and include existing
`answer_text` values so the business clarification workflow can resume after a
browser refresh. Anonymous callers receive `401`, unrelated users and callers
of ownerless legacy private tasks receive `403`, and missing tasks receive
`404`. Questions and clarification answers are not included in public `TaskRead`
responses.

`QuestionRead`: `{ "id": 1, "task_id": 1, "question_text": "string", "answer_text": "string|null", "order": 1 }`.

### `POST /tasks` — authenticated

Request: `{ "draft_text": "string", "topic": "string|null", "organization_id": 1 }` (`organization_id` is optional when the user belongs to exactly one organization).

The user must belong to the selected organization. If `organization_id` is omitted, no memberships returns `409` instructing the user to create or join an organization; multiple memberships returns `409` requiring an explicit ID. A user who is not a member receives `403`. The server records the organization and current user as task ownership/attribution.

Response `201`: `{ "task": TaskRead, "questions": [Question] }`. The task is created in `clarifying` + `unpublished` status and at least three questions are returned. A client-supplied `publication_status` is rejected.

### `PATCH /tasks/{id}/answers` — authenticated organization member

Request: `{ "answers": ["answer"] }` or `{ "answers": { "question key": "answer" } }`

Response: `Task` with the generated editable card and `card_ready` status.

### `PATCH /tasks/{id}` — authenticated organization member

Request: any subset of editable card fields (`title`, `context`, `need`, `users`, `data_materials`, `constraints`, `expected_result`, `success_criteria`, `contact`, `interaction_format`, `topic`). Task `status` and `publication_status` cannot be changed through this endpoint; either field returns `422`.

Response: `Task`.

### `POST /tasks/{id}/confirm` — authenticated organization member

Request: `{}`

Response: `TaskRead` with recalculated `rating_score`, `rating_breakdown`, `readiness_level`, `confirmed` status, and its publication state. First confirmation of an unpublished `card_ready` task also publishes it for compatibility. Reconfirmation recalculates rating but preserves `unpublished`, `published`, or `archived` state. A non-confirmed archived task returns `409` until restored with unpublish.

Task lifecycle transitions are `draft` → `clarifying` → `card_ready` → `confirmed`. Task creation continues to start at `clarifying`; confirmation requires `card_ready`. Reconfirming an already confirmed task is idempotent.

### `GET /tasks/{id}/rating` — public for published tasks; otherwise authenticated organization member

Response: `{ "score": 0, "readiness_level": "draft", "breakdown": { "context+need": 0, "data_materials": 0, "expected_result": 0, "success_criteria": 0, "constraints": 0, "users": 0, "contact+interaction_format": 0 }, "missing_fields": ["context"], "suggestions": ["Add context"] }` (readiness is `draft`, `working`, `ready`, or `priority`; `suggestions` gives actionable guidance for each missing field.) Public visibility requires both confirmed content status and published publication status. Private responses include `Cache-Control: private, no-store`.

### `GET /tasks` — public

The versioned route `GET /api/v1/tasks` supports `topic`, `readiness_level`, `min_rating`, `max_rating`, `q`, `sort`, `page`, and `page_size`. Ratings are integers from `0` to `100`; when both bounds are supplied, `min_rating` must not exceed `max_rating`. Readiness must be `draft`, `working`, `ready`, or `priority`. `q` is trimmed and case-insensitively searches title, context, need, expected result, and topic; blank search is ignored. Sort supports `rating`, `newest`, and `oldest`, defaulting to `newest`. Ties are ordered deterministically by ID. Invalid values return `422`.

The versioned response is the pagination envelope described above. The unversioned route retains its array response and existing `topic`, `readiness_level`, and `sort=rating` behavior.

Response: `[TaskRead]` containing only tasks whose content status is `confirmed` and publication status is `published`.

Unpublished and archived confirmed tasks are excluded from public results, search, filters, and count totals. Confirmed legacy tasks without an organization are public only when published. Ownerless private legacy tasks remain inaccessible through normal product routes; they are never adopted by the current user.

`TaskRead`: `{ "id": 1, "title": "string|null", "context": "string|null", "need": "string|null", "users": "string|null", "data_materials": "string|null", "constraints": "string|null", "expected_result": "string|null", "success_criteria": "string|null", "contact": "string|null", "interaction_format": "string|null", "topic": "string|null", "status": "confirmed", "publication_status": "published", "rating_score": 0, "rating_breakdown": {}, "readiness_level": "draft", "created_at": "datetime|null", "updated_at": "datetime|null" }`

### Publication actions

`POST /tasks/{id}/publish`, `POST /tasks/{id}/unpublish`, and `POST /tasks/{id}/archive` are also available under `/api/v1/tasks/{id}/...`. Each requires an authenticated member of the task's organization and a valid CSRF token. Requests have no body and return `200 TaskRead`. Publishing a non-confirmed task returns `409`; unpublish and archive preserve content status and existing proposals. Repeating the current action is idempotent.

### Browser proxy paths

The Vite and Nginx browser proxies preserve `/api/v1/...` when forwarding to FastAPI. Legacy `/api/...` paths strip the `/api` prefix. Both proxy routes preserve query strings, cookies, CSRF headers, response status, and cache headers.

Publication actions return the same `TaskRead`. They do not modify content, questions, answers, rating, ownership, or proposal history.

`Question`: `{ "id": 1, "task_id": 1, "question_text": "string", "answer_text": "string|null", "order": 1 }`

## Proposals

### `POST /tasks/{id}/proposals` — authenticated member of the selected team

Request: `{ "team_id": 1, "idea": "string", "plan": "string|null", "deadline": "string|null", "link": "string|null" }`

The task must be both confirmed and published. An otherwise authorized team member gets `409` when it is unpublished, archived, or not confirmed. The current user must belong to the selected team or receives `403`. The server sets `submitted_by_user_id` from the current session. Response `201`: `Proposal` with `pending` status.

### `GET /tasks/{id}/proposals` — authenticated member of the task's organization

The versioned route supports `page`, `page_size`, and an optional `status` (`pending`, `accepted`, or `rejected`). It returns the pagination envelope. Only an organization member may list a task's proposals. Team members cannot list competitor proposals. Tasks without an organization cannot use this product route. The unversioned route keeps its array response.

### `GET /api/v1/proposals/mine` — authenticated

Returns the current user's submitted proposal history as the standard
pagination envelope of `ProposalRead`. Inclusion is based strictly on
`submitted_by_user_id`; sharing a team with a proposal submitter does not grant
visibility to that proposal. Supports `page`, `page_size`, and `status`
(`ProposalStatus`); results are newest first with proposal ID as a stable
tie-breaker. Other users' proposals and organization-only proposal lists are
not returned by this endpoint.

### `PATCH /proposals/{id}` — authenticated member of the proposal task's organization

Request: `{ "status": "pending|accepted|rejected" }`

Only a member of the task's organization may decide a proposal; submitting it as a team member does not grant decision rights. Response: `Proposal`. This endpoint only changes a manually supplied status and never assigns a team automatically.

Proposal lifecycle transitions are `pending` → `accepted` or `pending` → `rejected`. Repeating `pending` is idempotent; `accepted` and `rejected` are terminal.

`Proposal`: `{ "id": 1, "task_id": 1, "team_id": 1, "idea": "string", "plan": "string|null", "deadline": "string|null", "link": "string|null", "status": "pending", "created_at": "datetime|null" }`

## Teams

### `POST /teams` — authenticated

Request: `{ "name": "string", "interests": "string|null", "skills": "string|null", "technologies": "string|null" }`

The server creates the team and its initial `owner` membership for the current user atomically. No user ID is accepted for ownership. Response `201`: `Team`.

### `GET /teams` — public

The versioned `GET /api/v1/teams` supports `page`, `page_size`, and `q`. Search is trimmed and case-insensitively checks name, interests, skills, and technologies. Its response is paginated. The unversioned route keeps its array response. Both contain only public profile fields; membership and account data are not returned.

### `GET /teams/mine` — authenticated

Available as `GET /api/v1/teams/mine?page=1&page_size=20`. Returns a paginated list of only the current user's team memberships, using the same safe public `Team` profile fields as the public catalog. This route is used when selecting a team for proposal submission; public team browsing does not imply membership. Missing or invalid sessions return `401`.

The business task list and clarification workflow, and the student's proposal
history, can now be reloaded after a browser refresh. The frontend reloads
server state on navigation; no notification or realtime updates are implied.

### `GET /teams/{id}` — public

Also available as `GET /api/v1/teams/{id}`. Returns the same safe `TeamRead` profile as the list. Missing teams return `404`.

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
