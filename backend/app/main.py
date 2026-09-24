from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import proposals, tasks, teams
from app.core import config
from app.core.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


def create_app(demo_enabled: bool | None = None, demo_token: str | None = None) -> FastAPI:
    enabled = config.DEMO_ADMIN_ENABLED if demo_enabled is None else demo_enabled
    token = config.DEMO_ADMIN_TOKEN if demo_token is None else demo_token
    from app.core.config import valid_demo_admin_token

    application = FastAPI(title="Hack Alem AI API", lifespan=lifespan)
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
        if request.url.path == "/admin/demo" or request.url.path.startswith("/admin/demo/"):
            result.headers["Cache-Control"] = "no-store"
            result.headers["X-Content-Type-Options"] = "nosniff"
            result.headers["X-Frame-Options"] = "DENY"
        return result

    application.include_router(tasks.router)
    application.include_router(proposals.router)
    application.include_router(teams.router)
    if enabled and valid_demo_admin_token(token):
        from app.api.routes.demo_admin import router
        application.include_router(router)
    return application


app = create_app()
