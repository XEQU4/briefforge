import hmac

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.routes import health
from app.core import config
from app.core.db import SessionLocal
from app.services.auth_security import hash_session_value, load_active_session


def create_app(demo_enabled: bool | None = None, demo_token: str | None = None) -> FastAPI:
    enabled = config.DEMO_ADMIN_ENABLED if demo_enabled is None else demo_enabled
    token = config.DEMO_ADMIN_TOKEN if demo_token is None else demo_token
    from app.core.config import valid_demo_admin_token

    application = FastAPI(title="BriefForge API")
    application.state.demo_admin_token = token
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def demo_security_headers(request, call_next):
        result = await call_next(request)
        if request.url.path.startswith(("/auth/", "/api/v1/auth/")):
            result.headers["Cache-Control"] = "no-store"
            result.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path == "/admin/demo" or request.url.path.startswith("/admin/demo/"):
            result.headers["Cache-Control"] = "no-store"
            result.headers["X-Content-Type-Options"] = "nosniff"
            result.headers["X-Frame-Options"] = "DENY"
        return result

    @application.middleware("http")
    async def csrf_protection(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            raw_session = request.cookies.get(config.SESSION_COOKIE_NAME)
            if raw_session and not request.url.path.startswith("/admin/demo"):
                async with SessionLocal() as db:
                    active = await load_active_session(db, raw_session)
                    if active is not None:
                        session, _user = active
                        csrf_cookie = request.cookies.get(config.CSRF_COOKIE_NAME, "")
                        csrf_header = request.headers.get("X-CSRF-Token", "")
                        if (
                            not csrf_cookie
                            or not csrf_header
                            or not hmac.compare_digest(csrf_cookie, csrf_header)
                            or not hmac.compare_digest(hash_session_value(csrf_header), session.csrf_token_hash)
                        ):
                            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
        return await call_next(request)

    @application.exception_handler(RequestValidationError)
    async def safe_validation_errors(request: Request, exc: RequestValidationError):
        if request.url.path.startswith(("/auth/", "/api/v1/auth/")):
            errors = [
                {key: value for key, value in error.items() if key not in {"input", "ctx", "url"}}
                for error in exc.errors()
            ]
            return JSONResponse(status_code=422, content={"detail": errors})
        return await request_validation_exception_handler(request, exc)

    application.include_router(health.router)
    application.include_router(api_router)
    if enabled and valid_demo_admin_token(token):
        from app.api.routes.demo_admin import router
        application.include_router(router)
    return application


app = create_app()
