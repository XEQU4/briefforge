# Backend integration

## Run

From `backend/`, install the existing requirements and start the API:

```sh
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The ML service defaults to `http://localhost:8001`, matching `ML/README.md`.
Set `ML_SERVICE_URL` to override that address, for example
`$env:ML_SERVICE_URL = 'http://127.0.0.1:8001'` in PowerShell or
`export ML_SERVICE_URL=http://127.0.0.1:8001` in a POSIX shell.

## ML request boundary

The public `topic` remains optional and nullable. When it is absent or blank,
the backend sends the neutral transport topic `Topic not specified` to the ML
service without replacing the stored task topic. Drafts over the upstream's
30,000 character limit, topics over 500 characters, or form-card question or
answer values over the upstream limits use the logged deterministic fallback;
the backend never truncates the stored user input.

Answers are persisted against this task's clarification questions. List input
is associated in question order; dictionary keys may be local question IDs or
exact question text. Partial dictionaries retain previously saved answers,
conflicting aliases return 422, and ML always receives all known answers keyed
by exact question text. The fallback maps only its own three fixed questions;
other answers remain saved without being assigned to a guessed card field.
Generated output fills blank card fields only. Any nonempty field is preserved,
regardless of whether it was generated or manually edited; the database does
not track that distinction. `PATCH /tasks/{id}` remains the way to edit or
clear fields intentionally. The ML response is restricted to its seven
supported card fields.

Connection failures, timeouts, upstream HTTP failures, invalid responses, and
inputs incompatible with the ML schema are logged by category. Fallbacks are
local deterministic results and are not presented as successful remote ML
generation. No draft, answer, contact detail, authorization header, or raw
upstream response is logged.

## Regression checks

Run the backend-local regression suite from `backend/`:

```sh
python -m unittest discover -s tests -v
```

Tests use a temporary SQLite database and mocked HTTP transports. They do not
test connectivity to a running ML service. The actual ML service must still be
started separately from `ML/` for a live integration check.

## Known limitations

- The backend deliberately does not infer card fields for nonstandard
  clarification questions when ML is unavailable.
- Existing nonempty card fields are preserved without recording their origin.
- The SQLite schema is created with `create_all`; no migration system is used.

## Private local demo admin

The optional local panel at `/admin/demo` is disabled by default. It is a
private demo helper, not production authentication. When enabled with a
valid `DEMO_ADMIN_ENABLED=true` and a URL-safe `DEMO_ADMIN_TOKEN` of at least
32 characters, it provides status and a one-time fixed `demo-v1` seed. The
seed adds 5 unconfirmed clarification drafts, 8 confirmed rated cards, 5
fictional teams, and 10 proposals. It makes no ML or network calls, never
selects a team, and does not reset or overwrite existing records. Repeated
seed requests return `already_seeded`. Its private API is described in
[DEMO_ADMIN_API.md](DEMO_ADMIN_API.md); future endpoint ideas are in
[API_PROPOSALS.md](API_PROPOSALS.md).

Generate a token locally with Docker (the daemon must be available):

```powershell
docker compose run --rm --no-deps backend python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:DEMO_ADMIN_TOKEN = 'paste-the-generated-value-here'
docker compose -f docker-compose.yml -f backend/compose.demo.yml up --build -d --no-deps backend
```

Open `http://localhost:8000/admin/demo` (or `/api/admin/demo` when using the
frontend proxy). Paste the token in the password field. It remains in page
memory and is sent only in `X-Demo-Admin-Token`. Do not put it in URLs or
commit it. Merely editing an env file does not update a running container;
recreate the backend. To disable the panel:

```powershell
docker compose -f docker-compose.yml up -d --no-deps --force-recreate backend
```

This recreates from the base Compose configuration, where the admin is
disabled by default. Restarting alone does not disable changed environment
settings. The demo dataset remains in the existing database volume.

Run the regression suite from `backend/` with
`python -m unittest discover -s tests -v`. It uses an isolated temporary
database and never touches the running demo database.
