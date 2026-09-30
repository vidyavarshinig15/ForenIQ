import asyncio
import os
from pathlib import Path
import pytest
from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory, engine, init_db
from backend.app.services.auth_service import AuthService

settings = get_settings()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes a clean database schema and bootstraps the initial admin for tests."""
    async def _setup():
        # Remove old sqlite test db if present for a fresh clean test run
        if "sqlite" in settings.DATABASE_URL:
            db_path = settings.DATABASE_URL.split("///")[-1]
            if db_path and Path(db_path).exists():
                try:
                    await engine.dispose()
                    os.remove(db_path)
                except Exception:
                    pass

        await init_db()
        async with async_session_factory() as session:
            auth_service = AuthService(session)
            await auth_service.ensure_bootstrap_admin()

    asyncio.run(_setup())
