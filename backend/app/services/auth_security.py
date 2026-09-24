import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models import AuthSession, User


_password_hasher = PasswordHasher(type=Type.ID)
_DUMMY_PASSWORD_HASH = _password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_login_password(password: str, password_hash: str | None) -> bool:
    # Keep unknown and legacy accounts on the same Argon2 verification path.
    return verify_password(password, password_hash or _DUMMY_PASSWORD_HASH) and password_hash is not None


def hash_session_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_session(db: AsyncSession, user_id: int) -> tuple[AuthSession, str, str]:
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    now = utcnow_naive()
    session = AuthSession(
        user_id=user_id,
        token_hash=hash_session_value(session_token),
        csrf_token_hash=hash_session_value(csrf_token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(seconds=config.SESSION_TTL_SECONDS),
    )
    db.add(session)
    await db.flush()
    return session, session_token, csrf_token


async def load_active_session(db: AsyncSession, raw_token: str | None) -> tuple[AuthSession, User] | None:
    if not raw_token or len(raw_token) > 256:
        return None
    session = await db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_value(raw_token)))
    if session is None or session.revoked_at is not None or session.expires_at <= utcnow_naive():
        return None
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return session, user
