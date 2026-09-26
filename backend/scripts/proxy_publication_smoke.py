"""Exercise versioned and legacy APIs through the running Nginx proxy.

Run inside the backend container with PROXY_BASE_URL, e.g.
PROXY_BASE_URL=http://host.docker.internal:18081 python scripts/proxy_publication_smoke.py
"""
import asyncio
import os
import uuid

import httpx


def require(response: httpx.Response, expected: int):
    assert response.status_code == expected, f"{response.request.method} {response.request.url.path}: expected {expected}, got {response.status_code}: {response.text}"
    return response


async def main() -> None:
    base = os.getenv("PROXY_BASE_URL", "http://host.docker.internal:8080").rstrip("/")
    suffix = uuid.uuid4().hex[:12]
    async with httpx.AsyncClient(base_url=base, timeout=45) as business, httpx.AsyncClient(base_url=base, timeout=45) as student:
        require(await business.post("/api/v1/auth/register", json={"email": f"proxy-business-{suffix}@example.com", "password": "Valid proxy test password 123!"}), 201)
        require(await student.post("/api/v1/auth/register", json={"email": f"proxy-student-{suffix}@example.com", "password": "Valid proxy test password 123!"}), 201)
        require(await business.get("/api/v1/auth/me"), 200)
        require(await business.get("/api/v1/tasks"), 200)
        for client in (business, student):
            csrf = client.cookies.get("briefforge_csrf")
            assert csrf, "registration did not provide a CSRF cookie"
            client.headers["X-CSRF-Token"] = csrf

        organization = require(await business.post("/api/v1/organizations", json={"name": "Proxy smoke", "slug": f"proxy-smoke-{suffix}"}), 201).json()
        team = require(await student.post("/api/v1/teams", json={"name": "Proxy smoke team"}), 201).json()
        my_teams = require(await student.get("/api/v1/teams/mine"), 200).json()
        assert [item["id"] for item in my_teams["items"]] == [team["id"]]
        created = require(await business.post("/api/v1/tasks", json={"draft_text": "A business needs a structured project challenge", "organization_id": organization["id"]}), 201).json()
        task_id = created["task"]["id"]
        require(await business.patch(f"/api/v1/tasks/{task_id}/answers", json={"answers": ["Clarify the business need", "Student teams", "A usable deliverable"]}), 200)
        require(await business.post(f"/api/v1/tasks/{task_id}/confirm", json={}), 200)
        proposal = require(await student.post(f"/api/v1/tasks/{task_id}/proposals", json={"team_id": team["id"], "idea": "A student team solution"}), 201).json()

        require(await business.post(f"/api/v1/tasks/{task_id}/unpublish", json={}), 200)
        public = require(await student.get("/api/v1/tasks", params={"q": "structured project"}), 200).json()
        assert task_id not in [item["id"] for item in public["items"]], "unpublished task remained in public catalog"
        private = require(await student.get(f"/api/v1/tasks/{task_id}"), 403)
        assert private.headers.get("content-type", "").startswith("application/json")
        require(await student.post(f"/api/v1/tasks/{task_id}/proposals", json={"team_id": team["id"], "idea": "Must be rejected"}), 409)
        require(await business.post(f"/api/v1/tasks/{task_id}/archive", json={}), 200)
        listing = require(await business.get(f"/api/v1/tasks/{task_id}/proposals", params={"page": 1}), 200).json()
        assert listing["total"] == 1 and listing["items"][0]["id"] == proposal["id"]
        require(await business.patch(f"/api/v1/proposals/{proposal['id']}", json={"status": "accepted"}), 200)

        # Check the two legacy rewrite aliases and the admin path stay JSON API requests.
        require(await business.get("/api/auth/me"), 200)
        legacy_tasks = require(await business.get("/api/tasks", params={"q": "structured project"}), 200)
        assert isinstance(legacy_tasks.json(), list)
        admin = await business.get("/api/admin/demo/status")
        assert admin.headers.get("content-type", "").startswith("application/json"), "admin API path fell through to SPA HTML"
    print("Nginx v1 and legacy proxy publication smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
