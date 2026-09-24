from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.db import get_db
from app.models import User
from app.services.auth_security import load_active_session


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias=config.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    active = await load_active_session(db, session_token)
    if active is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return active[1]


require_current_user = get_current_user
