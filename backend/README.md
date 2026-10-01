# Backend integration

## Run

The recommended complete installation is the [root Docker quick start](../README.md#quick-start).
For a standalone backend, use Python 3.12 in a virtual environment and an
accessible PostgreSQL instance. Before running the commands below, set
`DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB` in the process
environment, replacing the placeholders (`set DATABASE_URL=...` in Windows
CMD or `export DATABASE_URL=...` in a POSIX shell). For local HTTP, also set
`SESSION_COOKIE_SECURE=false` using the same shell syntax.

From `backend/`, install dependencies and apply migrations before starting the API:

```sh
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Outside Compose, the legacy `DATABASE_URL` default is
`sqlite+aiosqlite:///./app.db`. The migration chain targets PostgreSQL; that
SQLite default is not a supported fresh application installation. Isolated
tests create their own SQLite schema directly. Compose configures PostgreSQL
internally and does not publish its database port to the host. The application
does not create or upgrade tables on startup.

The standalone cookie default is secure; Compose already supplies the local
HTTP override. Keep
secure cookies enabled for HTTPS deployment. Root `.env` is consumed by
Compose, not automatically by a standalone backend process. `AVATAR_DIRECTORY`
defaults to `media/avatars` locally; Compose fixes it inside the media volume.

The ML service defaults to `http://localhost:8001`, matching `ml/README.md`.
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
started separately from `ml/` for a live integration check.

## Task publication workflow

Tasks retain their existing content lifecycle and have a separate
`publication_status` (`unpublished`, `published`, `archived`). Only confirmed
and published tasks appear in public catalogs or allow proposal submission.
Organization members control publication through the publish, unpublish, and
archive actions. The migration backfills existing confirmed tasks as published
to preserve their existing visibility, and other tasks as unpublished.

PostgreSQL locking and migration-backfill checks are available in
`scripts/postgres_publication_checks.py` and
`scripts/postgres_publication_migration.py`; run them only against a dedicated
throwaway database. `scripts/proxy_publication_smoke.py` exercises the live
Nginx proxy and publication workflow. These checks are separate from the SQLite
integration suite because SQLite does not provide PostgreSQL row-lock semantics.

## Known limitations

- The backend deliberately does not infer card fields for nonstandard
  clarification questions when ML is unavailable.
- Existing nonempty card fields are preserved without recording their origin.
- Schema changes are managed with Alembic migrations. SQLite remains available
  for isolated backend tests; the Docker development stack uses PostgreSQL.

## Application administrator

Register an account normally, then promote that existing account from an
operator shell (after applying migrations):

```sh
docker compose exec backend python scripts/set_admin.py user@example.com
```

Run Compose commands from the repository root. For a local backend environment,
run `python scripts/set_admin.py user@example.com` from `backend/` with the
intended `DATABASE_URL`. The command is idempotent and exits nonzero for a missing
account. It does not create users or passwords. The script ships in the backend
image; promotion does not require rebuilding or restarting a deployed container.
Refresh the signed-in browser after promotion and open **Admin** in the account
menu, or visit `/admin`.

To explicitly remove access as an operator:

```sh
docker compose exec backend python scripts/set_admin.py user@example.com --remove
```

Removal takes effect on the next admin API request. This operator command can
remove your own/last administrator flag; there is no web promotion or demotion.
The real panel uses session authentication and CSRF. It offers read-only
installation records plus activation/deactivation and session revocation for
other users. Deactivation revokes active sessions; reactivation requires a new
login. Your own account cannot be deactivated or have sessions revoked through
these admin actions. Admin access does not bypass product workspace membership.

The optional `/admin/demo` utility below remains independent: its local demo
token cannot grant real admin access, and an admin session cannot replace its
token.

## Private local demo admin

The optional local panel at `/admin/demo` is disabled by default. It is a
private demo helper, not production authentication. When enabled with a
valid `DEMO_ADMIN_ENABLED=true` and a URL-safe `DEMO_ADMIN_TOKEN` of at least
32 characters, it provides status and a one-time fixed `demo-v1` seed. The
seed adds 5 unconfirmed clarification drafts, 8 confirmed rated cards, 5
fictional teams, and 10 proposals. It makes no ML or network calls, never
selects a team, and does not reset or overwrite existing records. Repeated
seed requests return `already_seeded`. Its private API is described in
[DEMO_ADMIN_API.md](DEMO_ADMIN_API.md); historical endpoint proposals are in
[API_PROPOSALS.md](API_PROPOSALS.md).

Seed records are legacy, unowned examples, with no registered accounts or
workspace memberships. They demonstrate public catalog content; create normal
accounts, organizations, and teams to demonstrate authenticated editing and
proposal decisions.

Start the normal stack first. From the repository root, generate a token:

```sh
docker compose run --rm --no-deps backend python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set `DEMO_ADMIN_TOKEN` in the current shell: `set DEMO_ADMIN_TOKEN=VALUE` in
Windows CMD or `export DEMO_ADMIN_TOKEN=VALUE` in a POSIX shell, replacing
`VALUE` with the generated token. Then enable the overlay:

```sh
docker compose -f docker-compose.yml -f backend/compose.demo.yml up --build -d --no-deps backend
```

Open `http://localhost:8080/api/admin/demo` (adjust the frontend port if
overridden). The backend host port is not published by Compose. A standalone
backend exposes `/admin/demo` on its own port. Paste the token in the password field. It remains in page
memory and is sent only in `X-Demo-Admin-Token`. Do not put it in URLs or
commit it. Merely editing an env file does not update a running container;
recreate the backend. To disable the panel:

```sh
docker compose -f docker-compose.yml up -d --no-deps --force-recreate backend
```

This recreates from the base Compose configuration, where the admin is
disabled by default. Restarting alone does not disable changed environment
settings. The demo dataset remains in the existing database volume.

Run the regression suite from `backend/` with
`python -m unittest discover -s tests -v`. It uses an isolated temporary
database and never touches the running demo database.
