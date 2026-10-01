# Historical API proposals

These were early endpoint proposals. Several have since shipped; this list is retained as historical context. The current source of truth is [API_CONTRACT.md](../docs/API_CONTRACT.md).

- Task-card and team-profile reads are implemented, including `/api/v1` routes.
- Catalog search uses `q`; pagination uses `page` and `page_size`, not the originally proposed `search`, `limit`, and `offset` parameters.
- A standalone normal-product `GET /proposals/{id}` was not added. Proposal history and task proposal lists cover product workflows; real admin has a separate read-only proposal detail endpoint.
