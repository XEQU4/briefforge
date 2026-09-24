import atexit
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

_test_directory = tempfile.TemporaryDirectory(prefix="warspaceman-backend-tests-")
atexit.register(_test_directory.cleanup)
_database_path = Path(_test_directory.name) / "isolated.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_database_path.as_posix()}"

from app.core import config  # noqa: E402
from app.core.db import Base, SessionLocal, engine, get_db  # noqa: E402
from app.domain.status import ProposalStatus, TaskStatus  # noqa: E402
from app.main import app, create_app  # noqa: E402
from app.models import ClarifyingQuestion, Proposal, Task, Team  # noqa: E402,F401
from app.services import ai_client  # noqa: E402
from app.services.rating import calculate_rating, readiness_for_score  # noqa: E402
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # noqa: E402
from sqlalchemy import func, select  # noqa: E402


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
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        )
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
                await client.patch(f"/tasks/{seeded.id}", json={"title": "Manual edit survives"})
                repeat = await client.post("/admin/demo/seed", headers=headers)
                self.assertEqual(repeat.status_code, 200)
                self.assertEqual(repeat.json()["state"], "already_seeded")
                async with SessionLocal() as session:
                    current = await session.get(Task, seeded.id)
                    self.assertEqual(current.title, "Manual edit survives")
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

    async def _admin_request(self, application):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://testserver") as client:
            return await client.get("/admin/demo")


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
