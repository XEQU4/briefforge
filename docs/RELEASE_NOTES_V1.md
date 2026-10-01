# BriefForge v1.0.0

Prepared release notes; the tag and GitHub release have not been created.

## Highlights

- Complete business-to-student workflow: describe a need, clarify, edit a task card, publish, receive proposals, and make a manual decision.
- Deterministic readiness scoring with a breakdown and improvement guidance.
- Organization workspaces, public challenge/team catalogs, team creation, and proposal history.
- Session authentication, CSRF protection, editable profiles, and persistent validated avatars.
- Application admin with operational reads, account activation/deactivation, and session revocation; administrator privileges managed by an operator CLI.
- PostgreSQL persistence and automatic Alembic migrations.
- Optional OpenAI assistance and deterministic fallback without a provider key.
- Docker Compose startup with health checks and persistent database/media volumes.
- GitHub Actions for backend/ML tests, frontend builds, Compose configuration, and PostgreSQL migrations.

## Getting started

See the [README quick start](../README.md#quick-start). No API key, environment file, or seeded administrator password is required. Register normally, then use the documented CLI if administrator access is needed.

## Known limitations

- No password recovery, email verification/change, OAuth, invitations, notifications, or realtime messaging.
- Avatar media uses local Docker storage; cloud deployment, TLS, and backup automation are operator responsibilities.
- Fallback extraction is conservative and may need manual edits. Readiness measures brief completeness, not factual accuracy or feasibility.
- Unconfirmed cards can show a stored score of 0 in workspace lists until confirmation; the editor loads their current calculated readiness.
- Security controls have automated coverage, but the project has not been independently security-audited.

## Upgrade and data

The expected Alembic head is `d31b8f042a97`. Compose runs migrations before starting the backend. Back up the PostgreSQL and media volumes before upgrading an existing installation. Normal container recreation preserves them; `docker compose down -v` deletes them.
