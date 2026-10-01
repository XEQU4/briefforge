"""Focused release-candidate security boundaries; PostgreSQL races run separately."""
from test_integration import BackendTestCase, SessionLocal, config
from app.models import Proposal
from app.schemas.limits import MAX_DATABASE_ID, MAX_PAGE, MAX_PAGE_SIZE
from scripts.set_admin import set_admin


class SecurityRegressionTests(BackendTestCase):
    async def published_task_and_team(self):
        task = (await self.create_task())["task"]["id"]
        response = await self.client.patch(f"/tasks/{task}/answers", json={"answers": ["Need", "Users", "Success"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.post(f"/tasks/{task}/confirm")).status_code, 200)
        response = await self.client.post("/teams", json={"name": "Security regression team"})
        self.assertEqual(response.status_code, 201, response.text)
        return task, response.json()["id"]

    async def test_resource_ids_and_pagination_are_database_bounded(self):
        await set_admin(self.business_user.email)
        task, team = await self.published_task_and_team()
        proposal = (await self.client.post(f"/tasks/{task}/proposals", json={"team_id": team, "idea": "Idea"})).json()["id"]
        for prefix in ("", "/api/v1"):
            routes = [("GET", f"{prefix}/{resource}/{{id}}", None) for resource in ("tasks", "teams", "organizations")]
            routes += [("GET", f"{prefix}/tasks/{{id}}/{suffix}", None) for suffix in ("rating", "questions", "proposals")]
            routes += [("GET", f"{prefix}/organizations/{{id}}/tasks", None),
                       ("PATCH", f"{prefix}/tasks/{{id}}", {"title": "Valid"}),
                       ("PATCH", f"{prefix}/tasks/{{id}}/answers", {"answers": []}),
                       ("PATCH", f"{prefix}/proposals/{{id}}", {"status": "accepted"}),
                       ("POST", f"{prefix}/tasks/{{id}}/proposals", {"team_id": team, "idea": "Valid"})]
            routes += [("POST", f"{prefix}/tasks/{{id}}/{action}", None) for action in ("confirm", "publish", "unpublish", "archive")]
            for method, path, body in routes:
                for value in (0, -1, MAX_DATABASE_ID + 1, 10**30):
                    with self.subTest(method=method, path=path, value=value):
                        response = await self.client.request(method, path.format(id=value), json=body)
                        self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual((await self.client.get(f"{prefix}/tasks/{MAX_DATABASE_ID}")).status_code, 404)
        for resource in ("users", "organizations", "teams", "tasks", "proposals"):
            self.assertEqual((await self.client.get(f"/api/v1/admin/{resource}/{MAX_DATABASE_ID + 1}")).status_code, 422)
        for method, suffix, body in (("PATCH", "", {"is_active": True}), ("POST", "/revoke-sessions", None)):
            response = await self.client.request(method, f"/api/v1/admin/users/{MAX_DATABASE_ID + 1}{suffix}", json=body)
            self.assertEqual(response.status_code, 422, response.text)
        for path, key in (("tasks", "organization_id"), ("proposals", "task_id"), ("proposals", "team_id"), ("proposals", "submitted_by_user_id"), ("sessions", "user_id")):
            self.assertEqual((await self.client.get(f"/api/v1/admin/{path}", params={key: MAX_DATABASE_ID + 1})).status_code, 422)
        self.assertEqual((await self.client.post("/tasks", json={"organization_id": MAX_DATABASE_ID + 1, "draft_text": "Valid"})).status_code, 422)
        self.assertEqual((await self.client.post(f"/tasks/{task}/proposals", json={"team_id": MAX_DATABASE_ID + 1, "idea": "Valid"})).status_code, 422)
        paths = ["tasks", "teams", "teams/mine", "proposals/mine", f"organizations/{self.business_org.id}/tasks", f"tasks/{task}/proposals"]
        paths += [f"admin/{resource}" for resource in ("users", "organizations", "teams", "tasks", "proposals", "sessions")]
        self.assertLessEqual((MAX_PAGE - 1) * MAX_PAGE_SIZE, MAX_DATABASE_ID)
        for path in paths:
            for params in ({"page": 0}, {"page": MAX_PAGE + 1}, {"page": 10**30}, {"page_size": 0}, {"page_size": MAX_PAGE_SIZE + 1}):
                with self.subTest(path=path, params=params):
                    response = await self.client.get("/api/v1/" + path, params=params)
                    self.assertEqual(response.status_code, 422, response.text)
            response = await self.client.get("/api/v1/" + path, params={"page": MAX_PAGE, "page_size": MAX_PAGE_SIZE})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.patch(f"/proposals/{proposal}", json={"status": "accepted"})).status_code, 200)

    async def test_varchar_limits_reject_overflow_and_accept_boundaries(self):
        task, team = await self.published_task_and_team()
        for field, maximum in (("title", 500), ("topic", 200), ("contact", 500), ("interaction_format", 500)):
            for length, expected in ((maximum, 200), (maximum + 1, 422)):
                response = await self.client.patch(f"/tasks/{task}", json={field: "x" * length})
                self.assertEqual(response.status_code, expected, response.text)
        for length, expected in ((200, 201), (201, 422)):
            self.assertEqual((await self.client.post("/tasks", json={"draft_text": "Valid", "topic": "x" * length})).status_code, expected)
            self.assertEqual((await self.client.post("/teams", json={"name": "x" * length})).status_code, expected)
        for field, maximum in (("deadline", 100), ("link", 1000)):
            for length, expected in ((maximum, 201), (maximum + 1, 422)):
                value = "x" * length if field == "deadline" else "https://example.com/" + "x" * (length - len("https://example.com/"))
                response = await self.client.post(f"/tasks/{task}/proposals", json={"team_id": team, "idea": "Valid", field: value})
                self.assertEqual(response.status_code, expected, response.text)
        for body in ({"name": "x" * 201, "slug": "valid"}, {"name": "Valid", "slug": "x" * 121}, {"name": "Valid", "slug": "Ⅷ" * 41}, {"name": "Valid", "slug": "!!!"}):
            response = await self.client.post("/organizations", json=body)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual((await self.client.patch("/api/v1/profile", json={"display_name": "x" * 201})).status_code, 422)

    async def test_csrf_rejects_malformed_header_and_cookie_before_comparison(self):
        token = self.client.headers.pop("X-CSRF-Token")
        for value in (None, "wrong", "a" * 42, "a" * 44, "a" * 43, b"caf\xc3\xa9", "a" * 42 + "!"):
            headers = {} if value is None else {"X-CSRF-Token": value}
            response = await self.client.patch("/api/v1/profile", json={"display_name": "Blocked"}, headers=headers)
            self.assertEqual(response.status_code, 403, response.text)
        session = self.client.cookies.get(config.SESSION_COOKIE_NAME)
        for cookie in (b"caf\xc3\xa9", b"a" * 42, b"a" * 43):
            header = config.SESSION_COOKIE_NAME.encode() + b"=" + session.encode() + b"; " + config.CSRF_COOKIE_NAME.encode() + b"=" + cookie
            response = await self.client.patch("/api/v1/profile", json={"display_name": "Blocked"}, headers={"Cookie": header, "X-CSRF-Token": token})
            self.assertEqual(response.status_code, 403, response.text)
        response = await self.client.patch("/api/v1/profile", json={"display_name": "Allowed"}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["display_name"], "Allowed")

    async def test_proposal_links_require_absolute_web_urls_but_legacy_reads_work(self):
        task, team = await self.published_task_and_team()
        for link in ("https://example.com", "http://example.com", "HTTPS://example.com/path?q=1#part", "", None):
            response = await self.client.post(f"/tasks/{task}/proposals", json={"team_id": team, "idea": "Valid", "link": link})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["link"], link)
        for link in ("javascript:alert(1)", "data:text/html,test", "file:///etc/passwd", "vbscript:msgbox(1)", "//example.com", "/relative", "example.com", "https://", "https:///example.com", "http:example.com", "https://exa mple.com", "https://example.com\n", "https://example.com\\path", "https://[invalid", "https://example.com:99999"):
            with self.subTest(link=link):
                response = await self.client.post(f"/tasks/{task}/proposals", json={"team_id": team, "idea": "Valid", "link": link})
                self.assertEqual(response.status_code, 422, response.text)
        async with SessionLocal() as db:
            legacy = Proposal(task_id=task, team_id=team, submitted_by_user_id=self.business_user.id, idea="Legacy", link="javascript:alert(1)")
            db.add(legacy)
            await db.commit()
            legacy_id = legacy.id
        for path in (f"/tasks/{task}/proposals", f"/api/v1/tasks/{task}/proposals", "/api/v1/proposals/mine"):
            self.assertEqual((await self.client.get(path)).status_code, 200)
        self.assertEqual((await self.client.patch(f"/proposals/{legacy_id}", json={"status": "accepted"})).status_code, 200)

    async def test_private_reads_are_no_store_without_changing_public_catalog(self):
        task, _team = await self.published_task_and_team()
        await set_admin(self.business_user.email)
        for prefix in ("", "/api/v1"):
            paths = ["organizations/mine", f"organizations/{self.business_org.id}", f"organizations/{self.business_org.id}/tasks", "teams/mine", f"tasks/{task}/proposals", f"tasks/{task}/questions", f"tasks/{task}", f"tasks/{task}/rating"]
            for path in paths:
                response = await self.client.get(prefix + "/" + path)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers.get("cache-control"), "private, no-store", path)
            for path in ("tasks", "teams"):
                response = await self.client.get(prefix + "/" + path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("no-store", response.headers.get("cache-control", ""))
        for path in ("/api/v1/proposals/mine", "/api/v1/admin/users"):
            self.assertEqual((await self.client.get(path)).headers.get("cache-control"), "private, no-store")
        self.assertEqual((await self.client.get("/api/v1/auth/me")).headers.get("cache-control"), "no-store")
