"""Verify the admin flag migration on a disposable PostgreSQL database."""
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main(mode: str) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            if mode == "seed":
                await conn.execute(text("""
                    INSERT INTO users (email, display_name, password_hash, is_active, avatar_filename, created_at)
                    VALUES ('admin-migration@example.com', 'Existing user', 'existing-hash', false,
                            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.webp', '2026-01-01')
                """))
            elif mode in {"verify", "downgraded"}:
                row = (await conn.execute(text("""
                    SELECT display_name, password_hash, is_active, avatar_filename, created_at
                    FROM users WHERE email='admin-migration@example.com'
                """))).one()
                assert row.display_name == "Existing user" and row.password_hash == "existing-hash"
                assert not row.is_active and row.avatar_filename == "a" * 32 + ".webp"
                assert row.created_at.isoformat() == "2026-01-01T00:00:00"
                column = (await conn.execute(text("""
                    SELECT is_nullable, column_default FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='users' AND column_name='is_admin'
                """))).one_or_none()
                if mode == "verify":
                    assert column is not None and column.is_nullable == "NO" and column.column_default == "false"
                    assert (await conn.execute(text("SELECT count(*) FROM users WHERE is_admin IS NOT FALSE"))).scalar_one() == 0
                    savepoint = await conn.begin_nested()
                    default = (await conn.execute(text("""
                        INSERT INTO users (email) VALUES ('admin-default-check@example.com') RETURNING is_admin
                    """))).scalar_one()
                    assert default is False
                    await savepoint.rollback()
                else:
                    assert column is None
            else:
                raise ValueError("mode must be seed, verify, or downgraded")
        print(f"Admin migration {mode}: passed")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
