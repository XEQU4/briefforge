# Private local demo admin API

This is an opt-in, local demo tool. It is not authentication for the public API and must not be exposed to the internet. It is disabled by default. Enable it only on a trusted local demo backend with `DEMO_ADMIN_ENABLED=true` and a URL-safe token of at least 32 characters, generated with `secrets.token_urlsafe(32)`. There is no default token. When disabled or misconfigured, all three paths below return 404 and are omitted from OpenAPI. Public API routes are unchanged.

The admin page is available at both `GET /admin/demo` and `GET /admin/demo/`. It contains no embedded credential or data and makes no requests until a button is clicked. Paste the token into the password field; the browser keeps it in JavaScript memory only and sends it in `X-Demo-Admin-Token`. The page derives API URLs from its own pathname, so reverse-proxy prefixes are retained. Page and API responses set `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and `X-Frame-Options: DENY`.

All routes accept no request body. The API uses standard JSON error responses with a `detail` string. Count objects have exactly the integer keys `tasks`, `confirmed_tasks`, `drafts`, `teams`, and `proposals`.

| Method and path | Access | Response |
| --- | --- | --- |
| `GET /admin/demo[/]` | No token; only available when configured | `200 text/html`; local demo warning and controls |
| `GET /admin/demo/status` | `X-Demo-Admin-Token` required | `200` JSON: `{"enabled":true,"dataset_key":"demo-v1","version":"1","seeded":false,"counts":{"tasks":0,"confirmed_tasks":0,"drafts":0,"teams":0,"proposals":0}}`. Counts are current database totals; no record contents or paths are returned. |
| `POST /admin/demo/seed` | `X-Demo-Admin-Token` required | `201` first seed or `200` repeat: `{"dataset_id":"demo-v1","version":"1","state":"created","created_counts":{"tasks":13,"confirmed_tasks":8,"drafts":5,"teams":5,"proposals":10},"current_counts":{...}}`. Repeat uses `"state":"already_seeded"`; `current_counts` always reflects database totals. |

Missing, malformed, or incorrect token headers return the same `403` JSON error (`{"detail":"Invalid demo admin token"}`). Invalid admin configuration makes every admin URL return the standard `404`; a concurrent seed conflict without a committed manifest returns `409` with a retry message. No token is accepted from a URL, cookie, page source, or storage. The fixed `demo-v1` dataset contains 13 tasks total: five unconfirmed tasks with clarification questions and eight confirmed rated cards; it also contains five fictional teams and ten proposals. Four readiness bands are represented. Seed records use the existing deterministic rating service. Repeats do not alter the original records, even after manual edits. Seeding runs in one transaction. A unique database manifest key stores the exact created task, question, team, and proposal IDs plus creation metadata, protects concurrent requests, and allows rollback on failure. It does not call ML or any network service. The tool does not reset, delete, repair, or adopt records.

To generate a token inside the backend image, run from the repository root while Docker is available:

```powershell
docker compose run --rm --no-deps backend python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the resulting value in the local shell as `DEMO_ADMIN_TOKEN`, then start with the optional `backend/compose.demo.yml` overlay. Recreating the backend is required when changing the setting. See `backend/README.md` for enable/disable commands. Never commit or share the token.
