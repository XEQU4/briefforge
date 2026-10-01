from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.db import get_db
from app.models import User
from app.services.auth_security import load_active_session


async def get_optional_current_user(
    session_token: str | None = Cookie(default=None, alias=config.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    active = await load_active_session(db, session_token)
    return active[1] if active is not None else None


async def get_current_user(user: User | None = Depends(get_optional_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


require_current_user = get_current_user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
