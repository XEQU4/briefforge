import os
import re


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001").rstrip("/")
DEMO_ADMIN_ENABLED = os.getenv("DEMO_ADMIN_ENABLED", "false").strip().lower() == "true"
DEMO_ADMIN_TOKEN = os.getenv("DEMO_ADMIN_TOKEN", "")


def valid_demo_admin_token(token: str) -> bool:
    return len(token) >= 32 and re.fullmatch(r"[A-Za-z0-9_-]+", token) is not None
