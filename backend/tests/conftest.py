import asyncio
import os
from pathlib import Path
import pytest
from backend.app.core.config import get_settings
from backend.app.core.database import Base, async_session_factory, engine
from backend.app.services.auth_service import AuthService

# Ensure all models are registered with Base.metadata
from backend.app.models.user import User  # noqa
from backend.app.models.case import Case, CaseMember  # noqa
from backend.app.models.evidence import Evidence  # noqa
from backend.app.models.custody import EvidenceCustodyEvent  # noqa
from backend.app.models.audit import AuditLog  # noqa
from backend.app.models.processing_job import ProcessingJob  # noqa
from backend.app.models.raw_artifact import RawArtifact  # noqa
from backend.app.models.canonical_evidence import CanonicalEvidence  # noqa
from backend.app.models.evidence_embedding import EvidenceEmbedding  # noqa
from backend.app.models.search_history import SearchHistory  # noqa

settings = get_settings()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes a clean database schema and bootstraps the initial admin for tests."""
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_factory() as session:
            auth_service = AuthService(session)
            await auth_service.ensure_bootstrap_admin()

    asyncio.run(_setup())
