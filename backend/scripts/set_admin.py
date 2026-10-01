"""Operator-only administrator promotion/removal for an existing account."""
import argparse
import asyncio
from pathlib import Path
import sys

# Direct script execution must work both locally and in the backend container.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import SessionLocal, engine
from app.models import User


async def set_admin(email: str, *, remove: bool = False) -> bool:
    """Return False for a missing account; never create accounts or credentials."""
    normalized = email.strip().casefold()
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == normalized).with_for_update())
        if user is None:
            return False
        user.is_admin = not remove
        await db.commit()
        return True


async def run(email: str, remove: bool) -> int:
    try:
        if not await set_admin(email, remove=remove):
            print("User not found. Register the account first.", file=sys.stderr)
            return 1
        print("Admin access removed." if remove else "Admin access enabled.")
        return 0
    except SQLAlchemyError:
        print("Unable to update admin access. Check the database configuration and migrations.", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email of an existing registered account")
    parser.add_argument("--remove", action="store_true", help="Explicitly remove admin access (including your own)")
    args = parser.parse_args()
    return asyncio.run(run(args.email, args.remove))


if __name__ == "__main__":
    raise SystemExit(main())
