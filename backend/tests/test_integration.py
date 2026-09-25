import atexit
import importlib
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import httpx

_test_directory = tempfile.TemporaryDirectory(prefix="warspaceman-backend-tests-")
atexit.register(_test_directory.cleanup)
_database_path = Path(_test_directory.name) / "isolated.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_database_path.as_posix()}"
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from app.core import config  # noqa: E402
from app.core.db import Base, SessionLocal, engine, get_db  # noqa: E402
from app.domain.status import ProposalStatus, TaskPublicationStatus, TaskStatus  # noqa: E402
from app.main import app, create_app  # noqa: E402
from app.models import (  # noqa: E402,F401
    AuthSession, ClarifyingQuestion, Organization, OrganizationMember, OrganizationMemberRole,
    Proposal, Task, Team, TeamMember, TeamMemberRole, User,
)
from app.services import ai_client  # noqa: E402
from app.services.rating import calculate_rating, readiness_for_score  # noqa: E402
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402
from app.services.auth_security import hash_password, hash_session_value, utcnow_naive  # noqa: E402


QUESTIONS = [
    "What specific need or problem should this task address?",
    "Who are the intended users or beneficiaries?",
    "What result would show that the task is successful?",
]
CARD = {
    "context": "User supplied context",
    "need": "User supplied need",
    "users": "Analysts",
    "data_materials": None,
    "constraints": None,
    "expected_result": "A usable result",
    "success_criteria": None,
}


class BackendIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with engine.begin() as connection:
            if connection.dialect.name == "sqlite":
                await connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        raw_session = "integration-test-session-token"
        csrf_token = "integration-test-csrf-token"
        async with SessionLocal() as session:
            self.business_user = User(email="integration-business@example.com")
            self.business_org = Organization(name="Integration Business", slug="integration-business")
            session.add_all([self.business_user, self.business_org])
            await session.flush()
            session.add_all([
                OrganizationMember(
                    organization_id=self.business_org.id,
                    user_id=self.business_user.id,
                    role=OrganizationMemberRole.OWNER,
                ),
                AuthSession(
                    user_id=self.business_user.id,
                    token_hash=hash_session_value(raw_session),
                    csrf_token_hash=hash_session_value(csrf_token),
                    expires_at=utcnow_naive() + timedelta(days=1),
                ),
            ])
            await session.commit()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-CSRF-Token": csrf_token},
        )
        self.client.cookies.set(config.SESSION_COOKIE_NAME, raw_session, domain="testserver.local", path="/")
        self.client.cookies.set(config.CSRF_COOKIE_NAME, csrf_token, domain="testserver.local", path="/")
        self.requests = []
        self.ml_handler = self._success_handler
        self.ml_patch = patch.object(ai_client, "_new_ml_client", side_effect=self._ml_client)
        self.ml_patch.start()
        self.addAsyncCleanup(self._async_cleanup)

    async def _async_cleanup(self):
        self.ml_patch.stop()
        await self.client.aclose()
        await engine.dispose()

    def _ml_client(self, timeout):
        return httpx.AsyncClient(
            timeout=timeout, transport=httpx.MockTransport(self._recording_handler)
        )

    def _recording_handler(self, request):
        self.requests.append(request)
        return self.ml_handler(request)

    def _success_handler(self, request):
        if request.url.path == "/generate-questions":
            payload = json.loads(request.content)
            assert isinstance(payload["topic"], str) and payload["topic"].strip()
            return httpx.Response(200, json=QUESTIONS)
        if request.url.path == "/form-card":
            payload = json.loads(request.content)
            assert isinstance(payload["answers"], dict)
            assert set(payload["answers"]) == set(payload["questions"])
            return httpx.Response(200, json=CARD)
        raise AssertionError(f"Unexpected ML path {request.url.path}")

    async def create_task(self, topic=None, include_topic=True):
        body = {"draft_text": "A business needs a task card"}
        if include_topic:
            body["topic"] = topic
        response = await self.client.post("/tasks", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()
        self.assertGreaterEqual(len(data["questions"]), 3)
        return data

    async def new_registered_client(self, email: str):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        response = await client.post(
            "/auth/register",
            json={"email": email, "password": "a valid test password"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        csrf_token = client.cookies.get(config.CSRF_COOKIE_NAME)
        client.headers["X-CSRF-Token"] = csrf_token
        return client, response.json()

    async def test_task_lifecycle_enums_and_status_patch_is_rejected(self):
        created = await self.create_task()
        task_id = created["task"]["id"]
        self.assertEqual(created["task"]["status"], "clarifying")
        self.assertIsInstance(TaskStatus(created["task"]["status"]), TaskStatus)

        invalid = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual(invalid.status_code, 409)

        answered = await self.client.patch(
            f"/tasks/{task_id}/answers", json={"answers": ["Need", "Users", "Success"]}
        )
        self.assertEqual(answered.status_code, 200, answered.text)
        self.assertEqual(answered.json()["status"], "card_ready")

        status_patch = await self.client.patch(
            f"/tasks/{task_id}", json={"status": "confirmed"}
        )
        self.assertEqual(status_patch.status_code, 422)

        confirmed = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        self.assertEqual(
            (await self.client.post(f"/tasks/{task_id}/confirm", json={})).json()["status"],
            "confirmed",
        )

        schemas = app.openapi()["components"]["schemas"]
        self.assertEqual(
            schemas["TaskStatus"]["enum"],
            ["draft", "clarifying", "card_ready", "confirmed"],
        )
        self.assertEqual(
            schemas["ProposalStatus"]["enum"], ["pending", "accepted", "rejected"]
        )

    async def test_proposal_terminal_transitions(self):
        task = await self.create_task()
        task_id = task["task"]["id"]
        await self.client.patch(
            f"/tasks/{task_id}/answers", json={"answers": ["Need", "Users", "Success"]}
        )
        await self.client.post(f"/tasks/{task_id}/confirm", json={})
        team = await self.client.post("/teams", json={"name": "Lifecycle team"})
        team_id = team.json()["id"]

        async def submit_proposal(idea):
            response = await self.client.post(
                f"/tasks/{task_id}/proposals", json={"team_id": team_id, "idea": idea}
            )
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["status"], "pending")
            self.assertEqual(ProposalStatus(response.json()["status"]), ProposalStatus.PENDING)
            return response.json()["id"]

        accepted_id = await submit_proposal("Accepted idea")
        rejected_id = await submit_proposal("Rejected idea")
        pending_noop = await self.client.patch(
            f"/proposals/{accepted_id}", json={"status": "pending"}
        )
        self.assertEqual(pending_noop.status_code, 200)
        accepted = await self.client.patch(
            f"/proposals/{accepted_id}", json={"status": "accepted"}
        )
        rejected = await self.client.patch(
            f"/proposals/{rejected_id}", json={"status": "rejected"}
        )
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertEqual(rejected.json()["status"], "rejected")
        self.assertEqual(
            (await self.client.patch(f"/proposals/{accepted_id}", json={"status": "rejected"})).status_code,
            409,
        )
        self.assertEqual(
            (await self.client.patch(f"/proposals/{rejected_id}", json={"status": "accepted"})).status_code,
            409,
        )

    async def test_clarifying_question_task_order_is_unique(self):
        task = Task(context="Task", status=TaskStatus.CLARIFYING)
        task.questions.extend(
            [
                ClarifyingQuestion(question_text="First", order=1),
                ClarifyingQuestion(question_text="Duplicate", order=1),
            ]
        )
        async with SessionLocal() as session:
            session.add(task)
            with self.assertRaises(IntegrityError):
                await session.commit()
            await session.rollback()

    async def test_health_endpoints(self):
        async def unexpected_db_dependency():
            raise AssertionError("live health must not depend on the database")

        app.dependency_overrides[get_db] = unexpected_db_dependency
        try:
            live = await self.client.get("/health/live")
            self.assertEqual(live.status_code, 200)
            self.assertEqual(live.json(), {"status": "ok"})
        finally:
            app.dependency_overrides.pop(get_db, None)

        ready = await self.client.get("/health/ready")
        self.assertEqual(ready.status_code, 200, ready.text)
        self.assertEqual(ready.json(), {"status": "ready", "database": "ok"})

        class BrokenSession:
            async def execute(self, _statement):
                raise SQLAlchemyError(
                    "postgresql+asyncpg://user:secret@host/db SELECT secret_table"
                )

        async def failing_db():
            yield BrokenSession()

        app.dependency_overrides[get_db] = failing_db
        try:
            failed = await self.client.get("/health/ready")
        finally:
            app.dependency_overrides.pop(get_db, None)
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.json(), {"detail": "Database unavailable"})
        for sensitive_value in ("postgresql", "secret", "SELECT", "secret_table"):
            self.assertNotIn(sensitive_value, failed.text)

    async def test_topic_adaptation_override_and_create_serialization(self):
        data = await self.create_task(topic=None)
        self.assertIsNone(data["task"]["topic"])
        generated_request = self.requests[0]
        self.assertEqual(str(generated_request.url), f"{ai_client.ML_SERVICE_URL}/generate-questions")
        self.assertEqual(json.loads(generated_request.content)["topic"], ai_client.NEUTRAL_TOPIC)
        self.assertIsNotNone(data["task"]["created_at"])
        self.assertEqual([item["order"] for item in data["questions"]], [1, 2, 3])

        original_env = os.environ.get("ML_SERVICE_URL")
        try:
            with patch.dict(os.environ, {"ML_SERVICE_URL": "http://ml-override:9123"}):
                importlib.reload(config)
                self.assertEqual(config.ML_SERVICE_URL, "http://ml-override:9123")
        finally:
            if original_env is None:
                os.environ.pop("ML_SERVICE_URL", None)
            else:
                os.environ["ML_SERVICE_URL"] = original_env
            importlib.reload(config)

        with patch.object(ai_client, "ML_SERVICE_URL", "http://ml-override:9123"):
            await self.create_task(topic="Override")
            self.assertEqual(str(self.requests[-1].url), "http://ml-override:9123/generate-questions")

    async def test_list_id_and_text_answers_normalize_and_partial_merge(self):
        first = await self.create_task(include_topic=False)
        first_answers = ["Need one", "Users one", "Success one"]
        response = await self.client.patch(
            f"/tasks/{first['task']['id']}/answers", json={"answers": first_answers}
        )
        self.assertEqual(response.status_code, 200, response.text)
        sent = json.loads(self.requests[-1].content)["answers"]
        self.assertEqual(sent, dict(zip(QUESTIONS, first_answers)))

        second = await self.create_task(topic="Industry")
        question_ids = [item["id"] for item in second["questions"]]
        response = await self.client.patch(
            f"/tasks/{second['task']['id']}/answers",
            json={"answers": {str(question_ids[0]): "Need two"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(json.loads(self.requests[-1].content)["answers"][QUESTIONS[0]], "Need two")
        response = await self.client.patch(
            f"/tasks/{second['task']['id']}/answers",
            json={"answers": {QUESTIONS[1]: "Users two"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        sent = json.loads(self.requests[-1].content)["answers"]
        self.assertEqual(sent[QUESTIONS[0]], "Need two")
        self.assertEqual(sent[QUESTIONS[1]], "Users two")
        self.assertEqual(sent[QUESTIONS[2]], "")

        stored = await self.client.get(f"/tasks/{second['task']['id']}/rating")
        self.assertEqual(stored.status_code, 200)
        from app.core.db import SessionLocal

        async with SessionLocal() as session:
            result = await session.execute(
                select(ClarifyingQuestion).where(ClarifyingQuestion.task_id == second["task"]["id"])
            )
            saved = {item.question_text: item.answer_text for item in result.scalars()}
        self.assertEqual(saved[QUESTIONS[0]], "Need two")
        self.assertEqual(saved[QUESTIONS[1]], "Users two")

    async def test_text_key_alias_conflicts_unknown_and_order_independence(self):
        data = await self.create_task()
        qid = str(data["questions"][0]["id"])
        body = {"answers": {qid: "same", QUESTIONS[0]: "same"}}
        okay = await self.client.patch(f"/tasks/{data['task']['id']}/answers", json=body)
        self.assertEqual(okay.status_code, 200, okay.text)

        reversed_body = {"answers": {QUESTIONS[0]: "same", qid: "same"}}
        reversed_result = await self.client.patch(
            f"/tasks/{data['task']['id']}/answers", json=reversed_body
        )
        self.assertEqual(reversed_result.status_code, 200, reversed_result.text)
        self.assertEqual(okay.json()["need"], reversed_result.json()["need"])
        self.assertEqual(
            json.loads(self.requests[-1].content)["answers"],
            json.loads(self.requests[-2].content)["answers"],
        )

        calls_before = len(self.requests)
        conflict = await self.client.patch(
            f"/tasks/{data['task']['id']}/answers",
            json={"answers": {qid: "first", QUESTIONS[0]: "second"}},
        )
        unknown = await self.client.patch(
            f"/tasks/{data['task']['id']}/answers", json={"answers": {"999999": "bad"}}
        )
        self.assertEqual(conflict.status_code, 422)
        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(len(self.requests), calls_before)

    async def test_success_path_and_safe_ml_fallbacks_and_field_allowlist(self):
        data = await self.create_task()
        # A valid seven-field upstream response must be used without fallback.
        with patch.object(ai_client, "_extract_card", wraps=ai_client._extract_card) as fallback:
            response = await self.client.patch(
                f"/tasks/{data['task']['id']}/answers",
                json={"answers": dict(zip(QUESTIONS, ["Need", "Users", "Success"]))},
            )
            self.assertEqual(response.status_code, 200, response.text)
            fallback.assert_not_called()
        self.assertEqual(response.json()["status"], "card_ready")

        await self.client.patch(
            f"/tasks/{data['task']['id']}", json={"need": "Human edited value", "contact": "owner"}
        )
        self.ml_handler = lambda request: (
            httpx.Response(200, json=QUESTIONS)
            if request.url.path == "/generate-questions"
            else httpx.Response(
                200,
                json={**CARD, "need": None, "rating_score": 100, "status": "confirmed", "topic": "Injected"},
            )
        )
        response = await self.client.patch(
            f"/tasks/{data['task']['id']}/answers", json={"answers": {QUESTIONS[1]: "Changed users"}}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["need"], "Human edited value")
        self.assertEqual(response.json()["contact"], "owner")
        self.assertEqual(response.json()["status"], "card_ready")
        self.assertEqual(response.json()["rating_score"], 0)
        self.assertNotEqual(response.json()["topic"], "Injected")

        for handler in (
            lambda _: (_ for _ in ()).throw(httpx.ReadTimeout("test timeout")),
            lambda _: httpx.Response(200, content=b"not-json"),
            lambda _: httpx.Response(200, json={"unexpected": "shape"}),
        ):
            self.ml_handler = lambda request, failure=handler: (
                httpx.Response(200, json=QUESTIONS)
                if request.url.path == "/generate-questions"
                else failure(request)
            )
            response = await self.client.patch(
                f"/tasks/{data['task']['id']}/answers", json={"answers": {QUESTIONS[2]: "Saved result"}}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "card_ready")

        self.ml_handler = lambda request: httpx.Response(
            200, json=["one", "two"] if request.url.path == "/generate-questions" else CARD
        )
        fallback_task = await self.create_task(topic=None)
        self.assertGreaterEqual(len(fallback_task["questions"]), 3)

    async def test_end_to_end_manual_decision_rating_and_validation(self):
        early = await self.client.post("/tasks/999999/confirm", json={})
        self.assertEqual(early.status_code, 404)
        data = await self.create_task(topic="Energy")
        task_id = data["task"]["id"]
        premature = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual(premature.status_code, 409)
        answered = await self.client.patch(
            f"/tasks/{task_id}/answers",
            json={"answers": ["Need", "Users", "Success"]},
        )
        self.assertEqual(answered.status_code, 200, answered.text)
        edited = await self.client.patch(
            f"/tasks/{task_id}",
            json={
                "context": "Context",
                "need": "Need",
                "users": "Users",
                "data_materials": "Data",
                "constraints": "Constraints",
                "expected_result": "Result",
                "success_criteria": "Success",
                "contact": "Contact",
                "interaction_format": "Weekly meeting",
            },
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        confirmed = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        self.assertEqual(confirmed.json()["rating_score"], 100)
        rating = await self.client.get(f"/tasks/{task_id}/rating")
        self.assertEqual(rating.status_code, 200)
        self.assertEqual(rating.json()["score"], 100)
        self.assertEqual(sum(rating.json()["breakdown"].values()), 100)
        self.assertEqual(rating.json()["missing_fields"], [])

        rating_edit = await self.client.patch(f"/tasks/{task_id}", json={"data_materials": None})
        self.assertEqual(rating_edit.status_code, 200, rating_edit.text)
        self.assertEqual(rating_edit.json()["rating_score"], 80)
        self.assertEqual(rating_edit.json()["readiness_level"], "ready")
        self.assertIsNotNone(rating_edit.json()["updated_at"])

        low_data = await self.create_task(topic="Low readiness")
        low_id = low_data["task"]["id"]
        await self.client.patch(
            f"/tasks/{low_id}/answers", json={"answers": ["Need", "Users", "Success"]}
        )
        low_confirmed = await self.client.post(f"/tasks/{low_id}/confirm", json={})
        self.assertEqual(low_confirmed.status_code, 200, low_confirmed.text)
        self.assertLess(low_confirmed.json()["rating_score"], 80)

        listed = await self.client.get("/tasks?sort=rating")
        self.assertEqual(listed.status_code, 200)
        self.assertIn(task_id, [task["id"] for task in listed.json()])
        sorted_scores = [task["rating_score"] for task in listed.json()]
        self.assertEqual(sorted_scores, sorted(sorted_scores, reverse=True))
        self.assertIn(low_id, [task["id"] for task in listed.json()])
        self.assertEqual((await self.client.get("/tasks?readiness_level=unknown")).status_code, 422)
        self.assertEqual((await self.client.get("/tasks?sort=score")).status_code, 422)
        self.assertEqual(
            (await self.client.patch(f"/tasks/{task_id}/answers", json={"answers": ["late"]})).status_code,
            409,
        )

        team_response = await self.client.post("/teams", json={"name": "Team"})
        self.assertEqual(team_response.status_code, 201, team_response.text)
        team_id = team_response.json()["id"]
        missing_team = await self.client.post(
            f"/tasks/{task_id}/proposals", json={"team_id": 999999, "idea": "Idea"}
        )
        self.assertEqual(missing_team.status_code, 404)
        self.assertEqual(
            (await self.client.post("/tasks/999999/proposals", json={"team_id": team_id, "idea": "Idea"})).status_code,
            404,
        )
        proposal_response = await self.client.post(
            f"/tasks/{task_id}/proposals", json={"team_id": team_id, "idea": "Solution", "plan": "Plan"}
        )
        self.assertEqual(proposal_response.status_code, 201, proposal_response.text)
        proposal_id = proposal_response.json()["id"]
        self.assertEqual(proposal_response.json()["status"], "pending")
        listed_proposals = await self.client.get(f"/tasks/{task_id}/proposals")
        self.assertEqual(len(listed_proposals.json()), 1)
        accepted = await self.client.patch(
            f"/proposals/{proposal_id}", json={"status": "accepted"}
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertEqual((await self.client.patch("/proposals/999999", json={"status": "rejected"})).status_code, 404)
        self.assertEqual(
            (await self.client.patch(f"/proposals/{proposal_id}", json={"status": "accepted"})).status_code,
            409,
        )
        self.assertEqual((await self.client.get("/teams")).status_code, 200)
        self.assertEqual((await self.client.get("/tasks/999999/rating")).status_code, 404)
        self.assertEqual((await self.client.post("/tasks", json={"draft_text": "   "})).status_code, 422)
        self.assertEqual((await self.client.post("/teams", json={"name": "  "})).status_code, 422)
        self.assertEqual(
            (await self.client.post(f"/tasks/{task_id}/proposals", json={"team_id": team_id, "idea": "  "})).status_code,
            422,
        )

    async def test_unconfirmed_proposal_and_pending_idempotency(self):
        data = await self.create_task()
        team = await self.client.post("/teams", json={"name": "Proposal team"})
        response = await self.client.post(
            f"/tasks/{data['task']['id']}/proposals",
            json={"team_id": team.json()["id"], "idea": "Idea"},
        )
        self.assertEqual(response.status_code, 409)

        task_id = data["task"]["id"]
        await self.client.patch(
            f"/tasks/{task_id}/answers", json={"answers": ["Need", "Users", "Success"]}
        )
        await self.client.post(f"/tasks/{task_id}/confirm", json={})
        proposal = await self.client.post(
            f"/tasks/{task_id}/proposals",
            json={"team_id": team.json()["id"], "idea": "Idea"},
        )
        noop = await self.client.patch(
            f"/proposals/{proposal.json()['id']}", json={"status": "pending"}
        )
        self.assertEqual(noop.status_code, 200, noop.text)
        self.assertEqual(noop.json()["status"], "pending")

    async def test_private_demo_admin_disabled_and_seed_is_idempotent(self):
        disabled = create_app(demo_enabled=False, demo_token="")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=disabled), base_url="http://testserver") as client:
            for path in ("/admin/demo", "/admin/demo/", "/admin/demo/status", "/admin/demo/seed"):
                response = await (client.post(path) if path.endswith("seed") else client.get(path))
                self.assertEqual(response.status_code, 404)
            self.assertNotIn("/admin/demo/status", disabled.openapi()["paths"])

        token = "A" * 43
        with patch.dict(os.environ, {"DEMO_ADMIN_TOKEN": token}):
            enabled = create_app(demo_enabled=True, demo_token=token)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=enabled), base_url="http://testserver") as client:
                page = await client.get("/admin/demo")
                self.assertEqual(page.status_code, 200)
                self.assertIn("local demo", page.text.lower())
                self.assertNotIn(token, page.text)
                script = page.text.split("<script>", 1)[1].split("</script>", 1)[0]
                self.assertIn("async function call(", script)
                self.assertIn("onclick=()=>call('/status')", script)
                self.assertIn("onclick=()=>call('/seed','POST')", script)
                self.assertEqual(script.count("call('/status')"), 1)
                self.assertEqual(script.count("call('/seed','POST')"), 1)
                for header in ("cache-control", "x-content-type-options", "x-frame-options"):
                    self.assertIn(header, page.headers)
                self.assertEqual((await client.get("/admin/demo/status")).status_code, 403)
                self.assertEqual((await client.get("/admin/demo/status", headers={"X-Demo-Admin-Token": "bad"})).status_code, 403)
                before_calls = len(self.requests)
                headers = {"X-Demo-Admin-Token": token}
                status = await client.get("/admin/demo/status", headers=headers)
                self.assertEqual(status.status_code, 200, status.text)
                self.assertFalse(status.json()["seeded"])
                from app.core.db import SessionLocal
                async with SessionLocal() as session:
                    manual_team = Team(name="Manual record", interests="Demo")
                    session.add(manual_team)
                    await session.commit()
                    manual_team_id = manual_team.id
                first, second = await __import__("asyncio").gather(
                    client.post("/admin/demo/seed", headers=headers),
                    client.post("/admin/demo/seed", headers=headers),
                )
                self.assertTrue(all(result.status_code in (200, 201, 409) for result in (first, second)))
                self.assertIn(201, (first.status_code, second.status_code))
                self.assertEqual(len(self.requests), before_calls)
                result = first if first.status_code != 409 else second
                self.assertEqual(result.json()["created_counts"], {"tasks": 13, "confirmed_tasks": 8, "drafts": 5, "teams": 5, "proposals": 10})
                counts = {"tasks": 13, "confirmed_tasks": 8, "drafts": 5, "teams": 6, "proposals": 10}
                status = await client.get("/admin/demo/status", headers=headers)
                self.assertTrue(status.json()["seeded"])
                self.assertEqual(status.json()["counts"], counts)
                async with SessionLocal() as session:
                    self.assertIsNotNone(await session.get(Team, manual_team_id))
                catalog = await client.get("/tasks")
                self.assertEqual(len(catalog.json()), 8)
                self.assertEqual({item["readiness_level"] for item in catalog.json()}, {"draft", "working", "ready", "priority"})
                for item in catalog.json():
                    score, breakdown, _ = calculate_rating(type("RatingCard", (), item)())
                    self.assertEqual(item["rating_score"], score)
                    self.assertEqual(item["rating_breakdown"], breakdown)
                async with SessionLocal() as session:
                    seeded = (await session.execute(select(Task).where(Task.status == "confirmed"))).scalars().first()
                    original_title = seeded.title
                async with SessionLocal() as session:
                    seeded_task = await session.get(Task, seeded.id)
                    seeded_task.title = "Manual edit survives"
                    seeded_task.publication_status = TaskPublicationStatus.ARCHIVED
                    await session.commit()
                repeat = await client.post("/admin/demo/seed", headers=headers)
                self.assertEqual(repeat.status_code, 200)
                self.assertEqual(repeat.json()["state"], "already_seeded")
                async with SessionLocal() as session:
                    current = await session.get(Task, seeded.id)
                    self.assertEqual(current.title, "Manual edit survives")
                    self.assertEqual(current.publication_status, TaskPublicationStatus.ARCHIVED)
                    confirmed_states = (await session.scalars(
                        select(Task.publication_status).where(Task.status == TaskStatus.CONFIRMED)
                    )).all()
                    draft_states = (await session.scalars(
                        select(Task.publication_status).where(Task.status != TaskStatus.CONFIRMED)
                    )).all()
                    self.assertEqual(confirmed_states.count(TaskPublicationStatus.PUBLISHED), 7)
                    self.assertEqual(confirmed_states.count(TaskPublicationStatus.ARCHIVED), 1)
                    self.assertEqual(draft_states.count(TaskPublicationStatus.UNPUBLISHED), 5)
                    self.assertNotEqual(current.title, original_title)

    async def test_demo_admin_rejects_invalid_token_configuration(self):
        for token in ("", "short token", "non-url-safe-" + "!" * 30):
            response = await self._admin_request(create_app(demo_enabled=True, demo_token=token))
            self.assertEqual(response.status_code, 404)

    async def test_demo_seed_failure_rolls_back_all_fixture_rows(self):
        token = "B" * 43
        with patch.dict(os.environ, {"DEMO_ADMIN_TOKEN": token}), patch(
            "app.services.demo_seed._proposals", side_effect=RuntimeError("fixture failure")
        ):
            enabled = create_app(demo_enabled=True, demo_token=token)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=enabled, raise_app_exceptions=False),
                base_url="http://testserver",
            ) as client:
                response = await client.post("/admin/demo/seed", headers={"X-Demo-Admin-Token": token})
                self.assertEqual(response.status_code, 500)
        from app.models import DemoSeedManifest
        from app.core.db import SessionLocal
        async with SessionLocal() as session:
            for model in (DemoSeedManifest, Task, Team, Proposal):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model)), 0)

    async def test_auth_registration_hashes_credentials_and_returns_only_public_user(self):
        weak_password = "zebra123"
        weak = await self.client.post("/auth/register", json={"email": "weak@example.com", "password": weak_password})
        self.assertEqual(weak.status_code, 422)
        self.assertNotIn(weak_password, weak.text)
        whitespace = await self.client.post(
            "/auth/register", json={"email": "spaces@example.com", "password": "           "}
        )
        self.assertEqual(whitespace.status_code, 422)
        self.assertNotIn("           ", whitespace.text)

        password = "correct horse battery staple"
        response = await self.client.post(
            "/auth/register",
            json={"email": "  PERSON@Example.COM ", "password": password, "display_name": "Person"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        public_user = response.json()
        self.assertEqual(public_user["email"], "person@example.com")
        self.assertEqual(set(public_user), {"id", "email", "display_name", "created_at", "updated_at"})
        self.assertNotIn(password, response.text)
        self.assertNotIn("password_hash", response.text)

        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(item for item in cookies if item.startswith(config.SESSION_COOKIE_NAME + "="))
        csrf_cookie = next(item for item in cookies if item.startswith(config.CSRF_COOKIE_NAME + "="))
        self.assertIn("httponly", session_cookie.lower())
        self.assertIn("samesite=lax", session_cookie.lower())
        self.assertIn("path=/", session_cookie.lower())
        self.assertNotIn("httponly", csrf_cookie.lower())
        self.assertIn("samesite=lax", csrf_cookie.lower())
        self.assertIn("max-age=604800", session_cookie.lower())

        raw_session = self.client.cookies.get(config.SESSION_COOKIE_NAME)
        csrf_token = self.client.cookies.get(config.CSRF_COOKIE_NAME)
        async with SessionLocal() as session:
            user = await session.scalar(select(User).where(User.id == public_user["id"]))
            auth_session = await session.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
            self.assertTrue(user.password_hash.startswith("$argon2id$"))
            self.assertNotEqual(user.password_hash, password)
            self.assertEqual(auth_session.token_hash, hash_session_value(raw_session))
            self.assertNotEqual(auth_session.token_hash, raw_session)
            self.assertEqual(auth_session.csrf_token_hash, hash_session_value(csrf_token))
        self.assertNotIn(raw_session, response.text)

        duplicate = await self.client.post(
            "/auth/register",
            json={"email": "person@example.com", "password": password},
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(duplicate.status_code, 409)

    async def test_auth_login_generic_errors_and_inactive_user_rejection(self):
        password = "a valid sample password"
        async with SessionLocal() as session:
            active = User(email="active@example.com", password_hash=hash_password(password))
            inactive = User(email="inactive@example.com", password_hash=hash_password(password), is_active=False)
            legacy = User(email="legacy@example.com", password_hash=None)
            session.add_all([active, inactive, legacy])
            await session.commit()

        valid = await self.client.post("/auth/login", json={"email": "ACTIVE@example.com", "password": password})
        self.assertEqual(valid.status_code, 200, valid.text)
        self.assertEqual(valid.json()["email"], "active@example.com")
        self.assertNotIn("password_hash", valid.text)
        csrf = self.client.cookies.get(config.CSRF_COOKIE_NAME)
        self.client.headers["X-CSRF-Token"] = csrf
        valid_session_token = self.client.cookies.get(config.SESSION_COOKIE_NAME)
        async with SessionLocal() as session:
            user = await session.scalar(select(User).where(User.email == "active@example.com"))
            self.assertIsNotNone(user.last_login_at)
            self.assertIsNotNone(await session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_value(valid_session_token))))

        wrong = await self.client.post(
            "/auth/login", json={"email": "active@example.com", "password": "wrong password"},
            headers={"X-CSRF-Token": csrf},
        )
        unknown = await self.client.post(
            "/auth/login", json={"email": "unknown@example.com", "password": "wrong password"},
            headers={"X-CSRF-Token": csrf},
        )
        inactive = await self.client.post(
            "/auth/login", json={"email": "inactive@example.com", "password": password},
            headers={"X-CSRF-Token": csrf},
        )
        legacy = await self.client.post(
            "/auth/login", json={"email": "legacy@example.com", "password": password},
            headers={"X-CSRF-Token": csrf},
        )
        for result in (wrong, unknown, inactive, legacy):
            self.assertEqual(result.status_code, 401)
            self.assertEqual(result.json(), {"detail": "Invalid email or password"})

    async def test_auth_me_rejects_expired_revoked_inactive_and_malformed_sessions(self):
        password = "another valid password"
        async with SessionLocal() as session:
            user = User(email="session@example.com", password_hash=hash_password(password))
            session.add(user)
            await session.flush()
            expired = AuthSession(
                user_id=user.id, token_hash=hash_session_value("expired-token"), csrf_token_hash=hash_session_value("expired-csrf"),
                expires_at=utcnow_naive() - timedelta(seconds=1),
            )
            revoked = AuthSession(
                user_id=user.id, token_hash=hash_session_value("revoked-token"), csrf_token_hash=hash_session_value("revoked-csrf"),
                expires_at=utcnow_naive() + timedelta(hours=1), revoked_at=utcnow_naive(),
            )
            active = AuthSession(
                user_id=user.id, token_hash=hash_session_value("inactive-token"), csrf_token_hash=hash_session_value("inactive-csrf"),
                expires_at=utcnow_naive() + timedelta(hours=1),
            )
            session.add_all([expired, revoked, active])
            await session.commit()

        for token in ("expired-token", "revoked-token"):
            result = await self.client.get("/auth/me", cookies={config.SESSION_COOKIE_NAME: token})
            self.assertEqual(result.status_code, 401)
        self.client.cookies.set(config.SESSION_COOKIE_NAME, "%%% malformed")
        malformed = await self.client.get("/auth/me")
        self.assertEqual(malformed.status_code, 401)

        self.client.cookies.set(config.SESSION_COOKIE_NAME, "inactive-token")
        self.client.cookies.set(config.CSRF_COOKIE_NAME, "inactive-csrf")
        self.assertEqual((await self.client.get("/auth/me")).status_code, 200)
        async with SessionLocal() as session:
            user = await session.scalar(select(User).where(User.email == "session@example.com"))
            user.is_active = False
            await session.commit()
        self.assertEqual((await self.client.get("/auth/me")).status_code, 401)

    async def test_auth_logout_revokes_and_clears_cookies_idempotently(self):
        response = await self.client.post(
            "/auth/register", json={"email": "logout@example.com", "password": "a safe logout password"}
        )
        self.assertEqual(response.status_code, 201)
        raw_session = self.client.cookies.get(config.SESSION_COOKIE_NAME)
        csrf = self.client.cookies.get(config.CSRF_COOKIE_NAME)
        logout = await self.client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
        self.assertEqual(logout.status_code, 204)
        async with SessionLocal() as session:
            auth_session = await session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_value(raw_session)))
            self.assertIsNotNone(auth_session.revoked_at)
        self.assertIsNone(self.client.cookies.get(config.SESSION_COOKIE_NAME))
        self.assertIsNone(self.client.cookies.get(config.CSRF_COOKIE_NAME))
        self.assertEqual((await self.client.get("/auth/me")).status_code, 401)
        self.assertEqual((await self.client.post("/auth/logout")).status_code, 204)

    async def test_csrf_protection_applies_only_to_valid_cookie_sessions(self):
        registered = await self.client.post(
            "/auth/register", json={"email": "csrf@example.com", "password": "a csrf test password"}
        )
        self.assertEqual(registered.status_code, 201)
        csrf = self.client.cookies.get(config.CSRF_COOKIE_NAME)

        blocked = await self.client.post("/teams", json={"name": "Blocked"})
        self.assertEqual(blocked.status_code, 403)
        wrong = await self.client.post("/teams", json={"name": "Wrong"}, headers={"X-CSRF-Token": "wrong"})
        self.assertEqual(wrong.status_code, 403)
        allowed = await self.client.post("/teams", json={"name": "Allowed"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(allowed.status_code, 201, allowed.text)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as anonymous:
            public = await anonymous.post("/teams", json={"name": "Still public"})
            self.assertEqual(public.status_code, 401, public.text)

    async def test_organization_bootstrap_and_task_creation_membership_rules(self):
        alice, _alice_data = await self.new_registered_client("business-a@example.com")
        bob, _bob_data = await self.new_registered_client("business-b@example.com")
        anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        try:
            self.assertEqual((await anonymous.post("/organizations", json={"name": "No auth", "slug": "no-auth"})).status_code, 401)
            org_a = await alice.post("/organizations", json={"name": "Business A", "slug": "business-a"})
            self.assertEqual(org_a.status_code, 201, org_a.text)
            mine_a = await alice.get("/organizations/mine")
            self.assertEqual([item["id"] for item in mine_a.json()], [org_a.json()["id"]])
            async with SessionLocal() as session:
                owner_membership = await session.scalar(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == org_a.json()["id"],
                        OrganizationMember.user_id == _alice_data["id"],
                    )
                )
                self.assertEqual(owner_membership.role, OrganizationMemberRole.OWNER)

            one_org_task = await alice.post("/tasks", json={"draft_text": "A needs a structured challenge"})
            self.assertEqual(one_org_task.status_code, 201, one_org_task.text)
            async with SessionLocal() as session:
                created = await session.get(Task, one_org_task.json()["task"]["id"])
                self.assertEqual(created.organization_id, org_a.json()["id"])
                self.assertEqual(created.created_by_user_id, _alice_data["id"])

            org_a2 = await alice.post("/organizations", json={"name": "Business A Two", "slug": "business-a-two"})
            self.assertEqual(org_a2.status_code, 201, org_a2.text)
            ambiguous = await alice.post("/tasks", json={"draft_text": "Ambiguous organization"})
            self.assertEqual(ambiguous.status_code, 409)
            explicit = await alice.post(
                "/tasks", json={"draft_text": "Explicit organization", "organization_id": org_a2.json()["id"]}
            )
            self.assertEqual(explicit.status_code, 201, explicit.text)

            no_org = await bob.post("/tasks", json={"draft_text": "No organization yet"})
            self.assertEqual(no_org.status_code, 409)
            org_b = await bob.post("/organizations", json={"name": "Business B", "slug": "business-b"})
            self.assertEqual(org_b.status_code, 201, org_b.text)
            forbidden_create = await bob.post(
                "/tasks", json={"draft_text": "Cross organization", "organization_id": org_a.json()["id"]}
            )
            self.assertEqual(forbidden_create.status_code, 403)
            mine_b = await bob.get("/organizations/mine")
            self.assertEqual([item["id"] for item in mine_b.json()], [org_b.json()["id"]])
            self.assertEqual((await anonymous.post("/tasks", json={"draft_text": "Anonymous"})).status_code, 401)
        finally:
            await alice.aclose()
            await bob.aclose()
            await anonymous.aclose()

    async def test_task_mutations_require_organization_membership_and_keep_catalog_public(self):
        task_data = await self.create_task(topic="Authorization test")
        task_id = task_data["task"]["id"]
        member, member_data = await self.new_registered_client("business-member@example.com")
        unrelated, _unrelated_data = await self.new_registered_client("business-unrelated@example.com")
        anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        try:
            async with SessionLocal() as session:
                session.add(OrganizationMember(
                    organization_id=self.business_org.id,
                    user_id=member_data["id"],
                    role=OrganizationMemberRole.MEMBER,
                ))
                unrelated_org = Organization(name="Unrelated", slug="unrelated-business")
                session.add(unrelated_org)
                await session.flush()
                session.add(OrganizationMember(
                    organization_id=unrelated_org.id,
                    user_id=_unrelated_data["id"],
                    role=OrganizationMemberRole.OWNER,
                ))
                await session.commit()

            member_created = await member.post(
                "/tasks",
                json={"draft_text": "Member created task", "organization_id": self.business_org.id},
            )
            self.assertEqual(member_created.status_code, 201, member_created.text)
            async with SessionLocal() as session:
                member_task = await session.get(Task, member_created.json()["task"]["id"])
                self.assertEqual(member_task.created_by_user_id, member_data["id"])

            self.assertEqual((await anonymous.post("/tasks", json={"draft_text": "Anonymous"})).status_code, 401)
            self.assertEqual((await anonymous.patch(f"/tasks/{task_id}", json={"title": "Anonymous"})).status_code, 401)
            self.assertEqual((await anonymous.post("/teams", json={"name": "Anonymous"})).status_code, 401)
            self.assertEqual((await unrelated.patch(f"/tasks/{task_id}", json={"title": "Denied"})).status_code, 403)
            self.assertEqual((await unrelated.get(f"/tasks/{task_id}/rating")).status_code, 403)

            answered = await member.patch(
                f"/tasks/{task_id}/answers", json={"answers": ["Need", "Users", "Success"]}
            )
            self.assertEqual(answered.status_code, 200, answered.text)
            edited = await member.patch(f"/tasks/{task_id}", json={"need": "Member edit"})
            self.assertEqual(edited.status_code, 200, edited.text)
            confirmed = await member.post(f"/tasks/{task_id}/confirm", json={})
            self.assertEqual(confirmed.status_code, 200, confirmed.text)
            self.assertEqual((await unrelated.patch(f"/tasks/{task_id}", json={"title": "Denied"})).status_code, 403)
            self.assertEqual((await anonymous.get(f"/tasks/{task_id}/rating")).status_code, 200)
            catalog = await anonymous.get("/tasks")
            self.assertEqual([task["id"] for task in catalog.json()], [task_id])

            async with SessionLocal() as session:
                legacy_confirmed = Task(
                    title="Legacy public",
                    status=TaskStatus.CONFIRMED,
                    publication_status=TaskPublicationStatus.PUBLISHED,
                )
                legacy_draft = Task(title="Legacy private", status=TaskStatus.DRAFT)
                session.add_all([legacy_confirmed, legacy_draft])
                await session.commit()
                legacy_confirmed_id, legacy_draft_id = legacy_confirmed.id, legacy_draft.id
            legacy_catalog = await anonymous.get("/tasks")
            self.assertIn(legacy_confirmed_id, [task["id"] for task in legacy_catalog.json()])
            self.assertNotIn(legacy_draft_id, [task["id"] for task in legacy_catalog.json()])
            self.assertEqual((await anonymous.get(f"/tasks/{legacy_confirmed_id}/rating")).status_code, 200)
            self.assertEqual((await anonymous.get(f"/tasks/{legacy_draft_id}/rating")).status_code, 401)
            self.assertEqual((await self.client.patch(f"/tasks/{legacy_confirmed_id}", json={"title": "No adoption"})).status_code, 403)
            self.assertEqual((await self.client.post(f"/tasks/{legacy_draft_id}/confirm", json={})).status_code, 403)
        finally:
            await member.aclose()
            await unrelated.aclose()
            await anonymous.aclose()

    async def test_team_membership_controls_proposal_submission_visibility_and_decisions(self):
        task_data = await self.create_task(topic="Proposal authorization")
        task_id = task_data["task"]["id"]
        self.assertEqual((await self.client.patch(
            f"/tasks/{task_id}/answers", json={"answers": ["Need", "Users", "Success"]}
        )).status_code, 200)
        self.assertEqual((await self.client.post(f"/tasks/{task_id}/confirm", json={})).status_code, 200)

        student_a, student_a_data = await self.new_registered_client("student-a@example.com")
        student_b, student_b_data = await self.new_registered_client("student-b@example.com")
        business_b, business_b_data = await self.new_registered_client("business-proposals-b@example.com")
        business_c, business_c_data = await self.new_registered_client("business-proposals-c@example.com")
        outsider_student, _outsider_student_data = await self.new_registered_client("student-outsider@example.com")
        anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        try:
            team_a = await student_a.post("/teams", json={"name": "Student A Team", "interests": "Robotics"})
            team_b = await student_b.post("/teams", json={"name": "Student B Team"})
            self.assertEqual(team_a.status_code, 201, team_a.text)
            self.assertEqual(team_b.status_code, 201, team_b.text)
            async with SessionLocal() as session:
                owner = await session.scalar(select(TeamMember).where(TeamMember.team_id == team_a.json()["id"]))
                self.assertEqual(owner.user_id, student_a_data["id"])
                self.assertEqual(owner.role, TeamMemberRole.OWNER)
                session.add(TeamMember(
                    team_id=team_a.json()["id"], user_id=student_b_data["id"], role=TeamMemberRole.MEMBER
                ))
                business_org_b = Organization(name="Proposal Business B", slug="proposal-business-b")
                business_org_c = Organization(name="Proposal Business C", slug="proposal-business-c")
                session.add_all([business_org_b, business_org_c])
                await session.flush()
                session.add(OrganizationMember(
                    organization_id=business_org_b.id,
                    user_id=business_b_data["id"],
                    role=OrganizationMemberRole.OWNER,
                ))
                session.add_all([
                    OrganizationMember(
                        organization_id=self.business_org.id,
                        user_id=business_b_data["id"],
                        role=OrganizationMemberRole.MEMBER,
                    ),
                    OrganizationMember(
                        organization_id=business_org_c.id,
                        user_id=business_c_data["id"],
                        role=OrganizationMemberRole.OWNER,
                    ),
                ])
                await session.commit()

            self.assertEqual((await anonymous.post("/teams", json={"name": "Anonymous"})).status_code, 401)
            payload = {"team_id": team_a.json()["id"], "idea": "A proposal"}
            submitted = await student_a.post(f"/tasks/{task_id}/proposals", json=payload)
            self.assertEqual(submitted.status_code, 201, submitted.text)
            submitted_again = await student_a.post(f"/tasks/{task_id}/proposals", json={**payload, "idea": "Another proposal"})
            self.assertEqual(submitted_again.status_code, 201, submitted_again.text)
            member_submission = await student_b.post(f"/tasks/{task_id}/proposals", json=payload)
            self.assertEqual(member_submission.status_code, 201, member_submission.text)
            async with SessionLocal() as session:
                proposal = await session.get(Proposal, submitted.json()["id"])
                self.assertEqual(proposal.submitted_by_user_id, student_a_data["id"])
                member_proposal = await session.get(Proposal, member_submission.json()["id"])
                self.assertEqual(member_proposal.submitted_by_user_id, student_b_data["id"])

            self.assertEqual((await outsider_student.post(f"/tasks/{task_id}/proposals", json=payload)).status_code, 403)
            self.assertEqual((await anonymous.post(f"/tasks/{task_id}/proposals", json=payload)).status_code, 401)
            self.assertEqual((await student_a.get(f"/tasks/{task_id}/proposals")).status_code, 403)
            self.assertEqual((await business_c.get(f"/tasks/{task_id}/proposals")).status_code, 403)
            self.assertEqual((await anonymous.get(f"/tasks/{task_id}/proposals")).status_code, 401)
            listed = await self.client.get(f"/tasks/{task_id}/proposals")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(len(listed.json()), 3)

            self.assertEqual((await student_a.patch(f"/proposals/{submitted.json()['id']}", json={"status": "accepted"})).status_code, 403)
            self.assertEqual((await business_c.patch(f"/proposals/{submitted.json()['id']}", json={"status": "accepted"})).status_code, 403)
            self.assertEqual((await anonymous.patch(f"/proposals/{submitted.json()['id']}", json={"status": "accepted"})).status_code, 401)
            accepted = await self.client.patch(f"/proposals/{submitted.json()['id']}", json={"status": "accepted"})
            rejected = await business_b.patch(f"/proposals/{submitted_again.json()['id']}", json={"status": "rejected"})
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertEqual(accepted.json()["status"], "accepted")
            self.assertEqual(rejected.status_code, 200, rejected.text)
            self.assertEqual(rejected.json()["status"], "rejected")

            public_teams = await anonymous.get("/teams")
            self.assertEqual(public_teams.status_code, 200)
            self.assertEqual(set(public_teams.json()[0]), {"id", "name", "interests", "skills", "technologies"})
        finally:
            await student_a.aclose()
            await student_b.aclose()
            await business_b.aclose()
            await business_c.aclose()
            await outsider_student.aclose()
            await anonymous.aclose()

    async def test_v1_namespace_and_legacy_aliases(self):
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/auth/me", paths)
        self.assertIn("/auth/me", paths)
        self.assertIn("/health/live", paths)
        self.assertNotIn("/api/v1/health/live", paths)
        legacy_task_schema = paths["/tasks"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        versioned_task_schema = paths["/api/v1/tasks"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(legacy_task_schema["type"], "array")
        versioned_schema_name = versioned_task_schema["$ref"].rsplit("/", 1)[-1]
        versioned_task_schema = app.openapi()["components"]["schemas"][versioned_schema_name]
        self.assertEqual(set(versioned_task_schema["properties"]), {"items", "page", "page_size", "total", "pages"})
        self.assertEqual((await self.client.get("/api/v1/auth/me")).status_code, 200)
        public_team = await self.client.post("/teams", json={"name": "Versioned team"})
        self.assertEqual(public_team.status_code, 201, public_team.text)
        versioned_team = await self.client.get(f"/api/v1/teams/{public_team.json()['id']}")
        self.assertEqual(versioned_team.status_code, 200)
        self.assertEqual(set(versioned_team.json()), {"id", "name", "interests", "skills", "technologies"})

        legacy_teams = await self.client.get("/teams")
        versioned_teams = await self.client.get("/api/v1/teams")
        self.assertIsInstance(legacy_teams.json(), list)
        self.assertEqual(versioned_teams.json()["total"], 1)
        self.assertEqual(len(versioned_teams.json()["items"]), 1)

        legacy_tasks = await self.client.get("/tasks")
        versioned_tasks = await self.client.get("/api/v1/tasks")
        self.assertIsInstance(legacy_tasks.json(), list)
        self.assertEqual(set(versioned_tasks.json()), {"items", "page", "page_size", "total", "pages"})
        self.assertEqual((await self.client.get("/health/live")).status_code, 200)

    async def test_v1_task_get_authorization_pagination_search_filter_and_sort(self):
        outsider, _outsider_data = await self.new_registered_client("v1-outsider@example.com")
        anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        try:
            async with SessionLocal() as session:
                confirmed = [
                    Task(
                        title=title,
                        context=context,
                        topic=topic,
                        status=TaskStatus.CONFIRMED,
                        publication_status=TaskPublicationStatus.PUBLISHED,
                        rating_score=score,
                        readiness_level=level,
                        organization_id=self.business_org.id,
                    )
                    for title, context, topic, score, level in [
                        ("Alpha Research", "Needle in a Haystack", "Health", 90, "priority"),
                        ("Beta Design", "Better workflows", "Education", 70, "ready"),
                        ("Gamma Build", "Searchable Context", "Health", 40, "working"),
                    ]
                ]
                private = Task(
                    title="Hidden Draft",
                    status=TaskStatus.CLARIFYING,
                    organization_id=self.business_org.id,
                )
                legacy_private = Task(title="Legacy Draft", status=TaskStatus.CLARIFYING)
                session.add_all([*confirmed, private, legacy_private])
                await session.commit()
                for item in [*confirmed, private, legacy_private]:
                    await session.refresh(item)

            self.assertEqual((await anonymous.get(f"/api/v1/tasks/{private.id}")).status_code, 401)
            self.assertEqual((await outsider.get(f"/api/v1/tasks/{private.id}")).status_code, 403)
            self.assertEqual((await self.client.get(f"/api/v1/tasks/{private.id}")).status_code, 200)
            self.assertEqual((await self.client.get(f"/api/v1/tasks/{legacy_private.id}")).status_code, 403)
            self.assertEqual((await anonymous.get(f"/api/v1/tasks/{confirmed[0].id}")).status_code, 200)

            first = await anonymous.get("/api/v1/tasks", params={"page": 1, "page_size": 2})
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual((first.json()["total"], first.json()["pages"], len(first.json()["items"])), (3, 2, 2))
            second = await anonymous.get("/api/v1/tasks", params={"page": 2, "page_size": 2})
            self.assertEqual(second.json()["total"], 3)
            self.assertEqual(len(second.json()["items"]), 1)
            self.assertNotIn(private.id, [row["id"] for row in first.json()["items"] + second.json()["items"]])
            self.assertEqual((await anonymous.get("/api/v1/tasks", params={"page_size": 101})).status_code, 422)

            searched = await anonymous.get("/api/v1/tasks", params={"q": "  nEeDlE  "})
            self.assertEqual(searched.json()["total"], 1)
            self.assertEqual(searched.json()["items"][0]["id"], confirmed[0].id)
            empty_search = await anonymous.get("/api/v1/tasks", params={"q": "   "})
            self.assertEqual(empty_search.json()["total"], 3)
            filtered = await anonymous.get(
                "/api/v1/tasks", params={"topic": "Health", "readiness_level": "priority", "min_rating": 90, "max_rating": 90}
            )
            self.assertEqual(filtered.json()["total"], 1)
            self.assertEqual(filtered.json()["items"][0]["id"], confirmed[0].id)
            self.assertEqual((await anonymous.get("/api/v1/tasks", params={"min_rating": 80, "max_rating": 20})).status_code, 422)
            self.assertEqual((await anonymous.get("/api/v1/tasks", params={"sort": "random"})).status_code, 422)

            by_rating = await anonymous.get("/api/v1/tasks", params={"sort": "rating"})
            self.assertEqual([row["rating_score"] for row in by_rating.json()["items"]], [90, 70, 40])
            by_oldest = await anonymous.get("/api/v1/tasks", params={"sort": "oldest"})
            self.assertEqual([row["id"] for row in by_oldest.json()["items"]], sorted(row["id"] for row in by_oldest.json()["items"]))
            by_newest = await anonymous.get("/api/v1/tasks", params={"sort": "newest"})
            self.assertEqual([row["id"] for row in by_newest.json()["items"]], sorted((row["id"] for row in by_newest.json()["items"]), reverse=True))
            self.assertEqual((await anonymous.get("/api/v1/tasks", params={"min_rating": -1})).status_code, 422)
        finally:
            await outsider.aclose()
            await anonymous.aclose()

    async def test_v1_organization_team_search_and_proposal_pagination_authorization(self):
        outsider, _outsider_data = await self.new_registered_client("v1-org-outsider@example.com")
        anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        try:
            member_org = await self.client.get(f"/api/v1/organizations/{self.business_org.id}")
            self.assertEqual(member_org.status_code, 200)
            self.assertEqual((await outsider.get(f"/api/v1/organizations/{self.business_org.id}")).status_code, 403)
            self.assertEqual((await anonymous.get(f"/api/v1/organizations/{self.business_org.id}")).status_code, 401)
            self.assertEqual((await self.client.get("/api/v1/organizations/999999")).status_code, 404)

            team_a = await self.client.post("/teams", json={"name": "Robotics group", "skills": "CAD"})
            team_b = await self.client.post("/teams", json={"name": "Writing group", "interests": "Robotics journalism"})
            self.assertEqual(team_a.status_code, 201)
            self.assertEqual(team_b.status_code, 201)
            result = await anonymous.get("/api/v1/teams", params={"q": "ROBOTICS", "page_size": 1})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["total"], 2)
            self.assertEqual(len(result.json()["items"]), 1)
            self.assertEqual(set(result.json()["items"][0]), {"id", "name", "interests", "skills", "technologies"})
            self.assertEqual((await anonymous.get("/api/v1/teams/999999")).status_code, 404)

            async with SessionLocal() as session:
                task = Task(
                    title="Proposal catalog task", status=TaskStatus.CONFIRMED,
                    publication_status=TaskPublicationStatus.PUBLISHED,
                    organization_id=self.business_org.id, rating_score=50, readiness_level="working",
                )
                session.add(task)
                await session.flush()
                session.add_all([
                    Proposal(task_id=task.id, team_id=team_a.json()["id"], idea=f"Idea {index}", status=status)
                    for index, status in enumerate([ProposalStatus.PENDING, ProposalStatus.ACCEPTED, ProposalStatus.PENDING])
                ])
                await session.commit()
                task_id = task.id

            page = await self.client.get(f"/api/v1/tasks/{task_id}/proposals", params={"page_size": 2})
            self.assertEqual(page.status_code, 200, page.text)
            self.assertEqual((page.json()["total"], page.json()["pages"], len(page.json()["items"])), (3, 2, 2))
            pending = await self.client.get(f"/api/v1/tasks/{task_id}/proposals", params={"status": "pending"})
            self.assertEqual(pending.json()["total"], 2)
            self.assertEqual((await outsider.get(f"/api/v1/tasks/{task_id}/proposals")).status_code, 403)
            self.assertEqual((await anonymous.get(f"/api/v1/tasks/{task_id}/proposals")).status_code, 401)
            self.assertEqual((await self.client.get(f"/api/v1/tasks/{task_id}/proposals", params={"status": "unknown"})).status_code, 422)
        finally:
            await outsider.aclose()
            await anonymous.aclose()

    async def test_publication_transitions_and_first_confirmation_compatibility(self):
        created = await self.create_task(topic="Publication state machine")
        task_id = created["task"]["id"]
        self.assertEqual(created["task"]["publication_status"], "unpublished")
        forced = await self.client.post(
            "/tasks", json={"draft_text": "Cannot force publish", "publication_status": "published"}
        )
        self.assertEqual(forced.status_code, 422)
        patched = await self.client.patch(f"/tasks/{task_id}", json={"publication_status": "published"})
        self.assertEqual(patched.status_code, 422)
        self.assertEqual((await self.client.post(f"/api/v1/tasks/{task_id}/publish")).status_code, 409)

        archived_draft = await self.client.post(f"/tasks/{task_id}/archive", json={})
        self.assertEqual((archived_draft.status_code, archived_draft.json()["status"], archived_draft.json()["publication_status"]),
                         (200, "clarifying", "archived"))
        self.assertEqual((await self.client.post(f"/api/v1/tasks/{task_id}/confirm", json={})).status_code, 409)
        restored = await self.client.post(f"/api/v1/tasks/{task_id}/unpublish")
        self.assertEqual(restored.json()["publication_status"], "unpublished")

        answered = await self.client.patch(
            f"/api/v1/tasks/{task_id}/answers", json={"answers": ["Need", "Users", "Success"]}
        )
        self.assertEqual(answered.status_code, 200, answered.text)
        first_confirm = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual((first_confirm.json()["status"], first_confirm.json()["publication_status"]),
                         ("confirmed", "published"))

        unpublished = await self.client.post(f"/api/v1/tasks/{task_id}/unpublish")
        self.assertEqual(unpublished.json()["publication_status"], "unpublished")
        reconfirmed_unpublished = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual(reconfirmed_unpublished.json()["publication_status"], "unpublished")
        archived = await self.client.post(f"/api/v1/tasks/{task_id}/archive")
        self.assertEqual(archived.json()["publication_status"], "archived")
        reconfirmed_archived = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual(reconfirmed_archived.json()["publication_status"], "archived")
        async with SessionLocal() as session:
            archived_at = await session.scalar(select(Task.updated_at).where(Task.id == task_id))
        no_op_archive = await self.client.post(f"/api/v1/tasks/{task_id}/archive")
        self.assertEqual(no_op_archive.json()["publication_status"], "archived")
        async with SessionLocal() as session:
            self.assertEqual(await session.scalar(select(Task.updated_at).where(Task.id == task_id)), archived_at)
        archived_edit = await self.client.patch(f"/tasks/{task_id}", json={"title": "Edited while archived"})
        self.assertEqual(archived_edit.json()["publication_status"], "archived")
        published_again = await self.client.post(f"/tasks/{task_id}/publish")
        self.assertEqual(published_again.json()["publication_status"], "published")
        edited = await self.client.patch(f"/tasks/{task_id}", json={"title": "Still published"})
        self.assertEqual(edited.json()["publication_status"], "published")

        outsider, _ = await self.new_registered_client("publication-outsider@example.com")
        try:
            self.assertEqual((await outsider.post(f"/api/v1/tasks/{task_id}/archive")).status_code, 403)
            self.assertEqual((await outsider.post(f"/api/v1/tasks/{task_id}/publish")).status_code, 403)
        finally:
            await outsider.aclose()

    async def test_public_task_visibility_applies_to_catalog_detail_rating_and_counts(self):
        outsider, _ = await self.new_registered_client("visibility-outsider@example.com")
        anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        try:
            async with SessionLocal() as session:
                public_task = Task(
                    title="Visible publication marker", status=TaskStatus.CONFIRMED,
                    publication_status=TaskPublicationStatus.PUBLISHED, topic="visibility-special",
                    organization_id=self.business_org.id, rating_score=80, readiness_level="ready",
                )
                private_task = Task(
                    title="Hidden publication marker", status=TaskStatus.CONFIRMED,
                    publication_status=TaskPublicationStatus.UNPUBLISHED, topic="visibility-special",
                    organization_id=self.business_org.id, rating_score=70, readiness_level="ready",
                )
                archived_task = Task(
                    title="Archived publication marker", status=TaskStatus.CONFIRMED,
                    publication_status=TaskPublicationStatus.ARCHIVED, topic="visibility-special",
                    organization_id=self.business_org.id, rating_score=90, readiness_level="priority",
                )
                ownerless_private = Task(
                    title="Ownerless private marker", status=TaskStatus.CONFIRMED,
                    publication_status=TaskPublicationStatus.UNPUBLISHED,
                )
                session.add_all([public_task, private_task, archived_task, ownerless_private])
                await session.commit()
                for item in (public_task, private_task, archived_task, ownerless_private):
                    await session.refresh(item)

            legacy = await anonymous.get("/tasks", params={"q": "publication marker"})
            versioned = await anonymous.get("/api/v1/tasks", params={"q": "publication marker"})
            self.assertEqual([item["id"] for item in legacy.json()], [public_task.id])
            self.assertEqual(versioned.json()["total"], 1)
            self.assertEqual([item["id"] for item in versioned.json()["items"]], [public_task.id])
            for task in (private_task, archived_task, ownerless_private):
                for prefix in ("", "/api/v1"):
                    detail = await anonymous.get(f"{prefix}/tasks/{task.id}")
                    rating = await anonymous.get(f"{prefix}/tasks/{task.id}/rating")
                    self.assertEqual(detail.status_code, 401)
                    self.assertEqual(rating.status_code, 401)
            for task in (private_task, archived_task):
                detail = await self.client.get(f"/api/v1/tasks/{task.id}")
                rating = await self.client.get(f"/api/v1/tasks/{task.id}/rating")
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(rating.status_code, 200)
                self.assertEqual(detail.headers["cache-control"], "private, no-store")
                self.assertEqual(rating.headers["cache-control"], "private, no-store")
                self.assertEqual((await outsider.get(f"/api/v1/tasks/{task.id}")).status_code, 403)
                self.assertEqual((await outsider.get(f"/api/v1/tasks/{task.id}/rating")).status_code, 403)
            public_detail = await anonymous.get(f"/api/v1/tasks/{public_task.id}")
            public_rating = await anonymous.get(f"/api/v1/tasks/{public_task.id}/rating")
            self.assertEqual(public_detail.status_code, 200)
            self.assertEqual(public_detail.json()["publication_status"], "published")
            self.assertEqual(public_rating.status_code, 200)
        finally:
            await outsider.aclose()
            await anonymous.aclose()

    async def test_publication_preserves_proposals_and_csrf_on_both_prefixes(self):
        created = await self.create_task(topic="Publication proposal history")
        task_id = created["task"]["id"]
        await self.client.patch(f"/tasks/{task_id}/answers", json={"answers": ["Need", "Users", "Success"]})
        confirmed = await self.client.post(f"/tasks/{task_id}/confirm", json={})
        self.assertEqual(confirmed.json()["publication_status"], "published")
        team = await self.client.post("/teams", json={"name": "Publication member team"})
        proposal_response = await self.client.post(
            f"/api/v1/tasks/{task_id}/proposals", json={"team_id": team.json()["id"], "idea": "Preserve this"}
        )
        self.assertEqual(proposal_response.status_code, 201, proposal_response.text)
        proposal_id = proposal_response.json()["id"]

        csrf = self.client.headers.get("X-CSRF-Token")
        self.client.headers.pop("X-CSRF-Token", None)
        blocked_v1 = await self.client.post(f"/api/v1/tasks/{task_id}/archive")
        blocked_legacy = await self.client.post(f"/tasks/{task_id}/unpublish")
        self.assertEqual((blocked_v1.status_code, blocked_legacy.status_code), (403, 403))
        self.client.headers["X-CSRF-Token"] = csrf

        unpublish = await self.client.post(f"/api/v1/tasks/{task_id}/unpublish")
        self.assertEqual(unpublish.status_code, 200)
        rejected_submission = await self.client.post(
            f"/tasks/{task_id}/proposals", json={"team_id": team.json()["id"], "idea": "Must reject"}
        )
        self.assertEqual(rejected_submission.status_code, 409)
        legacy_public = await self.client.get("/tasks")
        v1_public = await self.client.get("/api/v1/tasks")
        self.assertNotIn(task_id, [item["id"] for item in legacy_public.json()])
        self.assertNotIn(task_id, [item["id"] for item in v1_public.json()["items"]])

        archive = await self.client.post(f"/tasks/{task_id}/archive")
        self.assertEqual(archive.json()["publication_status"], "archived")
        proposals = await self.client.get(f"/api/v1/tasks/{task_id}/proposals")
        self.assertEqual((proposals.status_code, proposals.json()["total"]), (200, 1))
        decision = await self.client.patch(f"/proposals/{proposal_id}", json={"status": "accepted"})
        self.assertEqual(decision.status_code, 200, decision.text)
        self.assertEqual(decision.json()["status"], "accepted")
        async with SessionLocal() as session:
            saved_proposal = await session.get(Proposal, proposal_id)
            self.assertEqual(saved_proposal.status, ProposalStatus.ACCEPTED)

    async def _admin_request(self, application):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://testserver") as client:
            return await client.get("/admin/demo")

    async def test_ownership_foundation_constraints_and_delete_policies(self):
        async with SessionLocal() as session:
            owner = User(email="  PERSON@Example.COM ", display_name="Person")
            organization = Organization(name="Acme", slug=" Acme & Co. ")
            team = Team(name="Team")
            session.add_all([owner, organization, team])
            await session.flush()
            self.assertEqual(owner.email, "person@example.com")
            self.assertEqual(organization.slug, "acme-co")

            task = Task(title="Legacy compatible", organization_id=organization.id, created_by_user_id=owner.id)
            proposal = Proposal(task=task, team=team, idea="Idea", submitted_by=owner)
            session.add_all([task, proposal])
            org_member = OrganizationMember(organization=organization, user=owner, role=OrganizationMemberRole.OWNER)
            team_member = TeamMember(team=team, user=owner, role=TeamMemberRole.OWNER)
            session.add_all([org_member, team_member])
            await session.commit()
            task_id, proposal_id, owner_id, organization_id, team_id = task.id, proposal.id, owner.id, organization.id, team.id

        # Email and slug normalization make case/spacing variants collide in DB constraints.
        async with SessionLocal() as session:
            session.add(User(email="PERSON@example.com"))
            with self.assertRaises(IntegrityError):
                await session.commit()
            await session.rollback()
            session.add(Organization(name="Duplicate", slug="ACME co"))
            with self.assertRaises(IntegrityError):
                await session.commit()
            await session.rollback()

        async with SessionLocal() as session:
            session.add(OrganizationMember(organization_id=organization_id, user_id=owner_id))
            with self.assertRaises(IntegrityError):
                await session.commit()
            await session.rollback()
            session.add(TeamMember(team_id=team_id, user_id=owner_id))
            with self.assertRaises(IntegrityError):
                await session.commit()
            await session.rollback()

        # Multiple proposals per team/task remain supported by existing API behavior.
        async with SessionLocal() as session:
            session.add(Proposal(task_id=task_id, team_id=team_id, idea="Second idea"))
            legacy_task = Task(title="No owner links")
            session.add(legacy_task)
            await session.commit()
            self.assertIsNone(legacy_task.organization_id)
            self.assertIsNone(legacy_task.created_by_user_id)

        async with SessionLocal() as session:
            organization_to_delete = await session.get(Organization, organization_id)
            await session.delete(organization_to_delete)
            with self.assertRaises(IntegrityError):
                await session.flush()
            await session.rollback()
            team_to_delete = await session.get(Team, team_id)
            await session.delete(team_to_delete)
            with self.assertRaises(IntegrityError):
                await session.flush()
            await session.rollback()
            task_to_delete = await session.get(Task, task_id)
            await session.delete(task_to_delete)
            with self.assertRaises(IntegrityError):
                await session.flush()
            await session.rollback()
            await session.execute(delete(User).where(User.id == owner_id))
            await session.commit()
            retained_task = await session.get(Task, task_id)
            retained_proposal = await session.get(Proposal, proposal_id)
            self.assertIsNotNone(retained_task)
            self.assertIsNotNone(retained_proposal)
            self.assertIsNone(retained_task.created_by_user_id)
            self.assertIsNone(retained_proposal.submitted_by_user_id)

        async with SessionLocal() as session:
            new_user = User(email="membership@example.com")
            new_org = Organization(name="Disposable org", slug="disposable-org")
            new_team = Team(name="Disposable team")
            session.add_all([new_user, new_org, new_team])
            await session.flush()
            session.add_all([
                OrganizationMember(organization_id=new_org.id, user_id=new_user.id),
                TeamMember(team_id=new_team.id, user_id=new_user.id),
            ])
            await session.flush()
            await session.execute(delete(Organization).where(Organization.id == new_org.id))
            await session.execute(delete(Team).where(Team.id == new_team.id))
            await session.commit()
            self.assertEqual(await session.scalar(select(func.count()).select_from(OrganizationMember)), 1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(TeamMember)), 0)


class RatingUnitTests(unittest.TestCase):
    def test_rating_boundaries_and_breakdown(self):
        self.assertEqual([readiness_for_score(score) for score in (0, 39, 40, 69, 70, 89, 90, 100)],
                         ["draft", "draft", "working", "working", "ready", "ready", "priority", "priority"])
        task = Task(
            context="Context", need="Need", data_materials="Data", expected_result="Result",
            success_criteria="Success", constraints="Constraints", users="Users",
            contact="Contact", interaction_format="Meeting",
        )
        score, breakdown, missing = calculate_rating(task)
        self.assertEqual(score, 100)
        self.assertEqual(sum(breakdown.values()), score)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
