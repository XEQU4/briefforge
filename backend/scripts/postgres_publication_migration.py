"""Seed and verify the publication migration on a disposable PostgreSQL DB.

Usage from backend/: python scripts/postgres_publication_migration.py seed|verify
"""
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main(mode: str) -> None:
    url = __import__("os").environ["DATABASE_URL"]
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            if mode == "seed":
                confirmed = (await conn.execute(text("""
                    INSERT INTO tasks (title,status,rating_score,rating_breakdown,readiness_level)
                    VALUES ('__briefforge_migration_confirmed__','confirmed',0,'{}','draft') RETURNING id
                """))).scalar_one()
                draft = (await conn.execute(text("""
                    INSERT INTO tasks (title,status,rating_score,rating_breakdown,readiness_level)
                    VALUES ('__briefforge_migration_draft__','clarifying',0,'{}','draft') RETURNING id
                """))).scalar_one()
                team = (await conn.execute(text("INSERT INTO teams (name) VALUES ('migration fixture') RETURNING id"))).scalar_one()
                proposal = (await conn.execute(text("""
                    INSERT INTO proposals (task_id,team_id,idea,status)
                    VALUES (:task,:team,'pending proposal','pending') RETURNING id
                """), {"task": confirmed, "team": team})).scalar_one()
                print(f"Seeded migration fixtures: confirmed={confirmed}, draft={draft}, proposal={proposal}")
            elif mode == "verify":
                rows = (await conn.execute(text("SELECT id,title,publication_status FROM tasks WHERE title IN ('__briefforge_migration_confirmed__','__briefforge_migration_draft__')"))).all()
                actual = {row.title: row.publication_status for row in rows}
                assert actual == {"__briefforge_migration_confirmed__": "published", "__briefforge_migration_draft__": "unpublished"}, actual
                confirmed_id = next(row.id for row in rows if row.title == "__briefforge_migration_confirmed__")
                draft_id = next(row.id for row in rows if row.title == "__briefforge_migration_draft__")
                proposal = await conn.execute(text("SELECT status FROM proposals WHERE task_id=:task AND idea='pending proposal'"), {"task": confirmed_id})
                assert proposal.scalar_one() == "pending", "migration changed or removed an existing proposal"
                savepoint = await conn.begin_nested()
                try:
                    await conn.execute(text("UPDATE tasks SET publication_status='invalid' WHERE id=:id"), {"id": draft_id})
                except Exception:
                    await savepoint.rollback()
                else:
                    raise AssertionError("publication_status check constraint accepted invalid value")
                savepoint = await conn.begin_nested()
                try:
                    await conn.execute(text("UPDATE tasks SET status='clarifying', publication_status='published' WHERE id=:id"), {"id": draft_id})
                except Exception:
                    await savepoint.rollback()
                else:
                    raise AssertionError("published non-confirmed task violated no database constraint")
                print("Publication backfill and database constraints passed")
            else:
                raise ValueError("mode must be seed or verify")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
