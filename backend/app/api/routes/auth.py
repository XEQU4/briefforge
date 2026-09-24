from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core import config
from app.core.db import get_db
from app.models import AuthSession, User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.ownership import UserRead
from app.services.auth_security import create_session, hash_password, hash_session_value, utcnow_naive, verify_login_password


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    cookie_options = {
        "max_age": config.SESSION_TTL_SECONDS,
        "path": "/",
        "secure": config.SESSION_COOKIE_SECURE,
        "samesite": "lax",
    }
    response.set_cookie(config.SESSION_COOKIE_NAME, session_token, httponly=True, **cookie_options)
    response.set_cookie(config.CSRF_COOKIE_NAME, csrf_token, httponly=False, **cookie_options)


def _clear_session_cookies(response: Response) -> None:
    for cookie_name in (config.SESSION_COOKIE_NAME, config.CSRF_COOKIE_NAME):
        response.delete_cookie(
            cookie_name,
            path="/",
            secure=config.SESSION_COOKIE_SECURE,
            httponly=(cookie_name == config.SESSION_COOKIE_NAME),
            samesite="lax",
        )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    user = User(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_active=True,
    )
    db.add(user)
    try:
        await db.flush()
        _, session_token, csrf_token = await create_session(db, user.id)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from exc
    _set_session_cookies(response, session_token, csrf_token)
    return user


@router.post("/login", response_model=UserRead)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    normalized_email = str(payload.email).strip().casefold()
    user = await db.scalar(select(User).where(User.email == normalized_email))
    password_ok = verify_login_password(payload.password, user.password_hash if user is not None else None)
    if user is None or not user.is_active or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user.last_login_at = utcnow_naive()
    _, session_token, csrf_token = await create_session(db, user.id)
    await db.commit()
    await db.refresh(user)
    _set_session_cookies(response, session_token, csrf_token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raw_token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if raw_token and len(raw_token) <= 256:
        session = await db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_value(raw_token)))
        if session is not None and session.revoked_at is None:
            session.revoked_at = utcnow_naive()
            await db.commit()
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
async def current_user(user: User = Depends(get_current_user)) -> User:
    return user
