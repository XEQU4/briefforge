"""Check terminal proposal decisions on isolated PostgreSQL, optionally through Nginx."""
import argparse
import asyncio
from pathlib import Path
import sys
import time
from uuid import uuid4

import httpx
from sqlalchemy import delete, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config
from app.core.db import SessionLocal, engine
from app.domain.status import ProposalStatus, TaskPublicationStatus, TaskStatus
from app.main import app
from app.models import Organization, OrganizationMember, OrganizationMemberRole, Proposal, Task, Team, User
from app.services.auth_security import create_session


async def wait_for_decisions() -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        async with SessionLocal() as db:
            count = await db.scalar(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database() AND wait_event_type = 'Lock'
                  AND query ILIKE '%proposals%'
            """))
        if count >= 2:
            return
        await asyncio.sleep(.05)
    raise AssertionError("Both proposal decisions must overlap while the fixture row is locked")


async def main(base_url: str | None = None) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Use an isolated PostgreSQL database for this check")
    suffix = uuid4().hex
    async with SessionLocal() as db:
        user = User(email=f"proposal-{suffix}@example.test")
        org = Organization(name="Proposal concurrency fixture", slug=f"proposal-{suffix}")
        team = Team(name="Proposal concurrency fixture")
        db.add_all([user, org, team])
        await db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrganizationMemberRole.OWNER))
        task = Task(title="Proposal concurrency fixture", organization_id=org.id, created_by_user_id=user.id,
                    status=TaskStatus.CONFIRMED, publication_status=TaskPublicationStatus.PUBLISHED)
        db.add(task)
        await db.flush()
        proposal = Proposal(task_id=task.id, team_id=team.id, idea="Pending decision", status=ProposalStatus.PENDING)
        db.add(proposal)
        _, session_token, csrf = await create_session(db, user.id)
        await db.commit()
        user_id, org_id, team_id, task_id, proposal_id = user.id, org.id, team.id, task.id, proposal.id

    pending = []
    client = httpx.AsyncClient(
        base_url=base_url or "http://proposal.test",
        transport=None if base_url else httpx.ASGITransport(app=app),
        cookies={config.SESSION_COOKIE_NAME: session_token, config.CSRF_COOKIE_NAME: csrf},
        headers={"X-CSRF-Token": csrf}, timeout=20,
    )
    try:
        async with SessionLocal() as blocker:
            await blocker.execute(select(Proposal.id).where(Proposal.id == proposal_id).with_for_update())
            pending = [asyncio.create_task(client.patch(f"/api/v1/proposals/{proposal_id}", json={"status": status}))
                       for status in ("accepted", "rejected")]
            try:
                await wait_for_decisions()
            finally:
                await blocker.rollback()
        responses = await asyncio.gather(*pending)
        assert sorted(response.status_code for response in responses) == [200, 409], [(r.status_code, r.text) for r in responses]
        winner = next(r.json()["status"] for r in responses if r.status_code == 200)
        async with SessionLocal() as db:
            final = await db.scalar(select(Proposal.status).where(Proposal.id == proposal_id))
            assert final.value == winner, (final, winner)
        opposite = "rejected" if winner == "accepted" else "accepted"
        repeated = await client.patch(f"/api/v1/proposals/{proposal_id}", json={"status": opposite})
        assert repeated.status_code == 409, (repeated.status_code, repeated.text)
        async with SessionLocal() as db:
            assert (await db.scalar(select(Proposal.status).where(Proposal.id == proposal_id))).value == winner
        print(f"PostgreSQL proposal decisions passed: 200 + 409; final={winner}; conflicting repeat=409")
    finally:
        for request in pending:
            if not request.done():
                request.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await client.aclose()
        async with SessionLocal() as db:
            await db.execute(delete(Proposal).where(Proposal.id == proposal_id))
            await db.execute(delete(Task).where(Task.id == task_id))
            await db.execute(delete(Team).where(Team.id == team_id))
            await db.execute(delete(Organization).where(Organization.id == org_id))
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Optional proxy URL; it must use the same isolated database")
    asyncio.run(main(parser.parse_args().base_url))
