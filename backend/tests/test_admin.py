"""Admin boundaries use the same isolated database/auth fixtures as product tests."""
import asyncio
from datetime import timedelta
import os
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
from sqlalchemy import select

from test_integration import BackendTestCase, SessionLocal, app, config, create_app
from app.domain.status import ProposalStatus, TaskPublicationStatus, TaskStatus
from app.models import AuthSession, Organization, OrganizationMember, OrganizationMemberRole, Proposal, Task, Team, TeamMember, TeamMemberRole, User
from app.services.auth_security import hash_session_value, utcnow_naive
from scripts.set_admin import set_admin


class AdminIntegrationTests(BackendTestCase):
    async def promote(self):
        self.assertTrue(await set_admin(self.business_user.email))

    def assert_safe(self, payload):
        forbidden = {"password_hash", "token_hash", "csrf_token_hash", "avatar_filename", "avatar_path"}
        if isinstance(payload, dict):
            self.assertFalse(forbidden.intersection(payload))
            for value in payload.values():
                self.assert_safe(value)
        elif isinstance(payload, list):
            for value in payload:
                self.assert_safe(value)

    async def test_admin_guard_enforces_all_routes_and_no_aliases(self):
        paths = ["/summary", "/users", "/users/1", "/organizations", "/organizations/1",
                 "/teams", "/teams/1", "/tasks", "/tasks/1", "/proposals", "/proposals/1", "/sessions"]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as anonymous:
            for path in paths:
                for client, expected in ((anonymous, 401), (self.client, 403)):
                    response = await client.get("/api/v1/admin" + path)
                    self.assertEqual(response.status_code, expected, response.text)
                    self.assertEqual(response.headers["cache-control"], "private, no-store")
            for client, expected in ((anonymous, 401), (self.client, 403)):
                self.assertEqual((await client.patch("/api/v1/admin/users/1", json={"is_active": False})).status_code, expected)
                self.assertEqual((await client.post("/api/v1/admin/users/1/revoke-sessions")).status_code, expected)
        await self.promote()
        self.assertEqual((await self.client.get("/api/v1/admin/summary")).status_code, 200)
        for path in ("/admin/summary", "/admin/users"):
            self.assertEqual((await self.client.get(path)).status_code, 404)
        for path in ("/auth/me", "/api/v1/auth/me"):
            self.assertTrue((await self.client.get(path)).json()["is_admin"])
        await set_admin(self.business_user.email, remove=True)
        self.assertEqual((await self.client.get("/api/v1/admin/summary")).status_code, 403)

    async def test_admin_bootstrap_cli_normalization_idempotence_remove_and_missing(self):
        root = Path(__file__).resolve().parents[1]
        async def cli(*args):
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(root / "scripts" / "set_admin.py"), *args,
                cwd=root, env=os.environ.copy(),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            output = (stdout + stderr).decode()
            self.assertNotIn("password", output.lower())
            self.assertNotIn("Traceback", output)
            return process.returncode, output
        for _ in range(2):
            code, output = await cli("  " + self.business_user.email.upper() + "  ")
            self.assertEqual(code, 0, output)
            self.assertIn("enabled", output)
        self.assertTrue((await self.client.get("/api/v1/auth/me")).json()["is_admin"])
        code, output = await cli(self.business_user.email, "--remove")
        self.assertEqual(code, 0, output)
        self.assertFalse((await self.client.get("/api/v1/auth/me")).json()["is_admin"])
        code, output = await cli("missing@example.com")
        self.assertNotEqual(code, 0)
        self.assertIn("not found", output)

    async def test_normal_registration_and_profile_cannot_grant_admin(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post("/api/v1/auth/register", json={
                "email": "not-admin@example.com", "password": "valid test password", "is_admin": True,
            })
            self.assertEqual(response.status_code, 201, response.text)
            self.assertFalse(response.json()["is_admin"])
            client.headers["X-CSRF-Token"] = client.cookies.get(config.CSRF_COOKIE_NAME)
            response = await client.patch("/api/v1/profile", json={"display_name": "Admin", "is_admin": True})
            self.assertEqual(response.status_code, 422)
            self.assertEqual((await client.get("/api/v1/admin/users")).status_code, 403)

    async def test_admin_users_search_filters_pagination_and_safe_details(self):
        await self.promote()
        async with SessionLocal() as db:
            db.add_all([
                User(email="alpha@example.com", display_name="Alpha", is_active=True, avatar_filename="a" * 32 + ".webp", password_hash="private-hash"),
                User(email="beta@example.com", display_name="Beta", is_active=False),
                User(email="percent@example.com", display_name="100% Person"),
            ])
            await db.commit()
        response = await self.client.get("/api/v1/admin/users", params={"sort": "email", "page_size": 2})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data["total"], data["pages"], len(data["items"])), (4, 2, 2))
        self.assertEqual([item["email"] for item in data["items"]], ["alpha@example.com", "beta@example.com"])
        self.assertTrue(data["items"][0]["has_avatar"])
        self.assert_safe(data)
        self.assertNotIn("private-hash", response.text)
        self.assertNotIn("a" * 32 + ".webp", response.text)
        second = (await self.client.get("/api/v1/admin/users", params={"sort": "email", "page_size": 2, "page": 2})).json()
        self.assertFalse({item["id"] for item in data["items"]} & {item["id"] for item in second["items"]})
        for params, total in (({"q": " ALPHA "}, 1), ({"q": "%"}, 1), ({"is_active": False}, 1), ({"is_admin": True}, 1), ({"is_active": True, "is_admin": False}, 2)):
            response = await self.client.get("/api/v1/admin/users", params=params)
            self.assertEqual(response.json()["total"], total, response.text)
        detail = await self.client.get(f"/api/v1/admin/users/{self.business_user.id}")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["organization_membership_count"], 1)
        self.assertEqual(detail.json()["active_session_count"], 1)
        self.assert_safe(detail.json())
        for params in ({"page": 0}, {"page_size": 101}, {"sort": "unsafe"}, {"q": "a" * 201}):
            self.assertEqual((await self.client.get("/api/v1/admin/users", params=params)).status_code, 422)

    async def test_admin_deactivate_reactivate_revokes_sessions_without_restoring_them(self):
        await self.promote()
        client, user = await self.new_registered_client("deactivate@example.com")
        try:
            response = await self.client.patch(f"/api/v1/admin/users/{user['id']}", json={"is_active": False})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(response.json()["is_active"])
            self.assertEqual((await client.get("/api/v1/auth/me")).status_code, 401)
            async with SessionLocal() as db:
                sessions = (await db.scalars(select(AuthSession).where(AuthSession.user_id == user["id"]))).all()
                self.assertTrue(all(session.revoked_at is not None for session in sessions))
            self.assertEqual((await client.post("/api/v1/auth/login", json={"email": user["email"], "password": "a valid test password"})).status_code, 401)
            response = await self.client.patch(f"/api/v1/admin/users/{user['id']}", json={"is_active": True})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual((await client.get("/api/v1/auth/me")).status_code, 401)
            self.assertEqual((await client.post("/api/v1/auth/login", json={"email": user["email"], "password": "a valid test password"})).status_code, 200)
        finally:
            await client.aclose()

    async def test_admin_user_mutation_allowlist_self_protection_and_csrf(self):
        await self.promote()
        path = f"/api/v1/admin/users/{self.business_user.id}"
        self.assertEqual((await self.client.patch(path, json={"is_active": False})).status_code, 409)
        self.assertEqual((await self.client.post(path + "/revoke-sessions")).status_code, 409)
        for key, value in {"email": "x@example.com", "password": "private-password", "display_name": "New", "is_admin": False, "avatar_filename": "../file", "created_at": "2020-01-01", "updated_at": "2020-01-01"}.items():
            response = await self.client.patch(path, json={"is_active": True, key: value})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn("input", response.json()["detail"][0])
        for value in ("false", 0, None):
            self.assertEqual((await self.client.patch(path, json={"is_active": value})).status_code, 422)
        self.assertEqual((await self.client.patch(path, json={})).status_code, 422)
        self.client.headers.pop("X-CSRF-Token")
        for response in (
            await self.client.patch(path, json={"is_active": False}),
            await self.client.post(path + "/revoke-sessions"),
        ):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertTrue((await self.client.get("/api/v1/auth/me")).json()["is_admin"])

    async def test_admin_revoke_sessions_is_idempotent_and_keeps_user_active(self):
        await self.promote()
        other, user = await self.new_registered_client("revoke@example.com")
        try:
            path = f"/api/v1/admin/users/{user['id']}/revoke-sessions"
            response = await self.client.post(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["revoked_count"], 1)
            self.assertEqual((await self.client.post(path)).json()["revoked_count"], 0)
            self.assertEqual((await other.get("/api/v1/auth/me")).status_code, 401)
            self.assertTrue((await self.client.get(f"/api/v1/admin/users/{user['id']}")).json()["is_active"])
            self.assertEqual((await self.client.get("/api/v1/admin/users/999999")).status_code, 404)
            self.assertEqual((await self.client.post("/api/v1/admin/users/999999/revoke-sessions")).status_code, 404)
        finally:
            await other.aclose()

    async def seed_admin_records(self):
        async with SessionLocal() as db:
            other = User(email="tenant@example.com", display_name="Other tenant")
            org = Organization(name="Other organization", slug="other-org")
            team = Team(name="Research team", interests="Health", skills="Python", technologies="SQL")
            db.add_all([other, org, team])
            await db.flush()
            task = Task(title="Private task", context="Private context", organization_id=org.id, created_by_user_id=other.id, status=TaskStatus.CARD_READY)
            published = Task(title="Published task", organization_id=org.id, created_by_user_id=other.id, status=TaskStatus.CONFIRMED, publication_status=TaskPublicationStatus.PUBLISHED, rating_score=80)
            db.add_all([task, published,
                OrganizationMember(organization_id=org.id, user_id=other.id, role=OrganizationMemberRole.OWNER),
                TeamMember(team_id=team.id, user_id=other.id, role=TeamMemberRole.OWNER)])
            await db.flush()
            proposal = Proposal(task_id=published.id, team_id=team.id, submitted_by_user_id=other.id, idea="An idea", plan="A plan", deadline="Next month", link="https://example.com")
            db.add(proposal)
            await db.commit()
            return {"user": other.id, "organization": org.id, "team": team.id, "task": task.id, "published": published.id, "proposal": proposal.id}

    async def test_admin_summary_entity_lists_details_and_normal_tenant_privacy(self):
        ids = await self.seed_admin_records()
        await self.promote()
        summary = (await self.client.get("/api/v1/admin/summary")).json()
        self.assertEqual(summary, {"users": 2, "active_users": 2, "organizations": 2, "teams": 1, "tasks": 2, "published_tasks": 1, "proposals": 1, "pending_proposals": 1, "active_sessions": 1})
        for section, id_key, params, counts in (
            ("organizations", "organization", {"q": "other-org"}, {"member_count": 1, "task_count": 2}),
            ("teams", "team", {"q": "python"}, {"member_count": 1, "proposal_count": 1}),
            ("tasks", "task", {"status": "card_ready", "organization_id": ids["organization"], "publication_status": "unpublished", "q": "Private"}, {"rating_score": 0}),
            ("proposals", "proposal", {"status": "pending", "task_id": ids["published"], "team_id": ids["team"], "submitted_by_user_id": ids["user"]}, {"idea": "An idea"}),
        ):
            response = await self.client.get("/api/v1/admin/" + section, params={**params, "page_size": 1})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["total"], 1)
            self.assertEqual(response.json()["items"][0]["id"], ids[id_key])
            for key, value in counts.items():
                self.assertEqual(response.json()["items"][0][key], value)
            detail = await self.client.get(f"/api/v1/admin/{section}/{ids[id_key]}")
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assert_safe(detail.json())
            for method in ("patch", "delete"):
                response = await getattr(self.client, method)(f"/api/v1/admin/{section}/{ids[id_key]}")
                self.assertEqual(response.status_code, 405)
        tasks = (await self.client.get("/api/v1/admin/tasks", params={"sort": "rating"})).json()
        self.assertEqual(tasks["items"][0]["id"], ids["published"])
        details = (await self.client.get(f"/api/v1/admin/users/{ids['user']}")).json()
        self.assertEqual([details[field] for field in ("organization_membership_count", "team_membership_count", "created_task_count", "submitted_proposal_count")], [1, 1, 2, 1])
        self.assertEqual((await self.client.get(f"/api/v1/tasks/{ids['task']}")).status_code, 403)
        self.assertEqual((await self.client.patch(f"/api/v1/tasks/{ids['task']}", json={"title": "Changed"})).status_code, 403)
        self.assertEqual((await self.client.get(f"/api/v1/organizations/{ids['organization']}")).status_code, 403)
        # Becoming an admin grants operational reads, not tenant workflow powers.
        self.assertEqual((await self.client.patch(f"/api/v1/proposals/{ids['proposal']}", json={"status": "accepted"})).status_code, 403)

    async def test_admin_sessions_derived_status_counts_and_no_hashes(self):
        await self.promote()
        now = utcnow_naive()
        async with SessionLocal() as db:
            inactive = User(email="inactive-session@example.com", is_active=False)
            db.add(inactive)
            await db.flush()
            for label, user_id, expires, revoked in (
                ("expired", self.business_user.id, now - timedelta(seconds=1), None),
                ("revoked", self.business_user.id, now + timedelta(days=1), now),
                ("inactive", inactive.id, now + timedelta(days=1), None),
            ):
                db.add(AuthSession(user_id=user_id, token_hash=hash_session_value(label), csrf_token_hash="private-csrf", expires_at=expires, revoked_at=revoked))
            await db.commit()
        response = await self.client.get("/api/v1/admin/sessions")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual({row["status"] for row in response.json()["items"]}, {"active", "expired", "revoked", "inactive"})
        self.assert_safe(response.json())
        self.assertNotIn("private-csrf", response.text)
        for state in ("active", "expired", "revoked", "inactive"):
            response = await self.client.get("/api/v1/admin/sessions", params={"status": state})
            self.assertEqual(response.json()["total"], 1, response.text)
        self.assertEqual((await self.client.get("/api/v1/admin/sessions", params={"q": "inactive-session", "user_id": inactive.id})).json()["total"], 1)
        summary = (await self.client.get("/api/v1/admin/summary")).json()
        self.assertEqual(summary["active_sessions"], 1)

    async def test_demo_token_and_real_admin_remain_isolated(self):
        token = "D" * 43
        enabled = create_app(demo_enabled=True, demo_token=token)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=enabled), base_url="http://testserver") as client:
            self.assertEqual((await client.get("/api/v1/admin/summary", headers={"X-Demo-Admin-Token": token})).status_code, 401)
            client.cookies.update(self.client.cookies)
            self.assertEqual((await client.get("/api/v1/admin/summary", headers={"X-Demo-Admin-Token": token})).status_code, 403)
            await self.promote()
            self.assertEqual((await client.get("/api/v1/admin/summary")).status_code, 200)
            self.assertEqual((await client.get("/admin/demo/status")).status_code, 403)
            self.assertEqual((await client.get("/admin/demo/status", headers={"X-Demo-Admin-Token": token})).status_code, 200)
            self.assertEqual((await client.post("/admin/demo/seed")).status_code, 403)
        self.assertEqual((await self.client.get("/admin/demo/status")).status_code, 404)

    async def test_admin_errors_remain_safe_and_non_cacheable(self):
        await self.promote()
        with patch("app.api.routes.admin.paginate", side_effect=RuntimeError("private SQL details")):
            response = await self.client.get("/api/v1/admin/users")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private SQL", response.text)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
