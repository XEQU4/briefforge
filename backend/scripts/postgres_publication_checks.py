"""Exercise publication/proposal row-lock ordering against PostgreSQL only."""
import asyncio
import sys
import time
from datetime import timedelta
from pathlib import Path

import httpx
from sqlalchemy import delete, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config
from app.core.db import SessionLocal, engine
from app.domain.status import TaskPublicationStatus, TaskStatus
from app.main import app
from app.models import AuthSession, Organization, OrganizationMember, OrganizationMemberRole, Proposal, Task, Team, TeamMember, TeamMemberRole, User
from app.services.auth_security import hash_session_value, utcnow_naive


async def wait_for_lock_waiters(expected: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        async with SessionLocal() as db:
            count = await db.scalar(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database() AND wait_event_type = 'Lock'
                  AND query ILIKE '%FOR UPDATE%'
            """))
        if count >= expected:
            return
        await asyncio.sleep(.05)
    raise AssertionError(f"timed out waiting for {expected} SELECT FOR UPDATE waiter(s)")


async def main() -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("These checks require PostgreSQL; refusing to run against another database")
    suffix = str(time.time_ns())
    raw_cookie, csrf = f"publication-{suffix}", f"csrf-{suffix}"
    async with SessionLocal() as db:
        user = User(email=f"publication-{suffix}@example.test")
        org = Organization(name="Publication concurrency fixture", slug=f"pub-{suffix}")
        team = Team(name="Publication concurrency fixture")
        db.add_all([user, org, team])
        await db.flush()
        db.add_all([
            OrganizationMember(organization_id=org.id, user_id=user.id, role=OrganizationMemberRole.OWNER),
            TeamMember(team_id=team.id, user_id=user.id, role=TeamMemberRole.OWNER),
            AuthSession(user_id=user.id, token_hash=hash_session_value(raw_cookie), csrf_token_hash=hash_session_value(csrf), expires_at=utcnow_naive() + timedelta(hours=1)),
        ])
        tasks = [Task(title=f"Concurrency {i}", status=TaskStatus.CONFIRMED, publication_status=TaskPublicationStatus.PUBLISHED, organization_id=org.id, created_by_user_id=user.id) for i in (1, 2)]
        db.add_all(tasks)
        await db.commit()
        org_id, team_id, user_id, task1, task2 = org.id, team.id, user.id, tasks[0].id, tasks[1].id
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://publication.test", headers={"X-CSRF-Token": csrf})
    client.cookies.set(config.SESSION_COOKIE_NAME, raw_cookie, domain="publication.test", path="/")
    client.cookies.set(config.CSRF_COOKIE_NAME, csrf, domain="publication.test", path="/")
    try:
        # A proposal waiting behind an archive sees the committed private state.
        blocker = await engine.connect()
        tx = await blocker.begin()
        await blocker.execute(text("UPDATE tasks SET publication_status='unpublished' WHERE id=:id"), {"id": task1})
        proposal = asyncio.create_task(client.post(f"/api/v1/tasks/{task1}/proposals", json={"team_id": team_id, "idea": "waiter"}))
        await wait_for_lock_waiters(1)
        await tx.commit()
        await blocker.close()
        response = await proposal
        assert response.status_code == 409, (response.status_code, response.text)

        # Proposal takes the row lock first; archive waits and then preserves it.
        blocker = await engine.connect()
        tx = await blocker.begin()
        await blocker.execute(text("SELECT id FROM tasks WHERE id=:id FOR UPDATE"), {"id": task2})
        proposal = asyncio.create_task(client.post(f"/api/v1/tasks/{task2}/proposals", json={"team_id": team_id, "idea": "committed before archive"}))
        await wait_for_lock_waiters(1)
        archive = asyncio.create_task(client.post(f"/api/v1/tasks/{task2}/archive", json={}))
        await wait_for_lock_waiters(2)
        await tx.commit()
        await blocker.close()
        proposal_response, archive_response = await asyncio.gather(proposal, archive)
        assert proposal_response.status_code == 201, (proposal_response.status_code, proposal_response.text)
        assert archive_response.status_code == 200, (archive_response.status_code, archive_response.text)
        async with SessionLocal() as db:
            stored = await db.scalar(select(Proposal).where(Proposal.task_id == task2))
            archived = await db.scalar(select(Task.publication_status).where(Task.id == task2))
            assert stored is not None and archived == TaskPublicationStatus.ARCHIVED
        print("PostgreSQL publication/proposal lock ordering passed")
    finally:
        await client.aclose()
        async with SessionLocal() as db:
            await db.execute(delete(Proposal).where(Proposal.task_id.in_([task1, task2])))
            await db.execute(delete(Task).where(Task.id.in_([task1, task2])))
            await db.execute(delete(Team).where(Team.id == team_id))
            await db.execute(delete(Organization).where(Organization.id == org_id))
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
