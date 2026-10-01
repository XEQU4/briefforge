"""Check avatar migration preservation on a disposable PostgreSQL database.

From backend/: python scripts/postgres_profile_migration.py seed|verify|downgraded
"""
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main(mode: str) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            if mode == "seed":
                await connection.execute(text("""
                    INSERT INTO users (email, display_name, password_hash, is_active, created_at)
                    VALUES ('avatar-migration@example.com', 'Existing account', 'existing-hash', true, '2026-01-01')
                """))
            elif mode in {"verify", "downgraded"}:
                row = (await connection.execute(text("""
                    SELECT email, display_name, password_hash, is_active, created_at
                    FROM users WHERE email='avatar-migration@example.com'
                """))).one()
                assert row.display_name == "Existing account" and row.password_hash == "existing-hash"
                assert row.is_active and row.created_at.isoformat() == "2026-01-01T00:00:00"
                columns = (await connection.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='users'
                """))).scalars().all()
                assert ("avatar_filename" in columns) == (mode == "verify")
                if mode == "verify":
                    count = (await connection.execute(text("SELECT count(*) FROM users WHERE avatar_filename IS NOT NULL"))).scalar_one()
                    assert count == 0, "Migration invented avatar references"
            else:
                raise ValueError("mode must be seed, verify, or downgraded")
        print(f"Avatar migration {mode}: passed")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
