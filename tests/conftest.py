"""Pytest configuration and fixtures for testing."""
import asyncio
import pytest
import pytest_asyncio
import sqlalchemy as sa
from typing import AsyncGenerator
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient

from app.database import Base
from app.config import settings
from app.models.user import User
from app.utils.auth import hash_password, create_access_token


# Test database URL (use same credentials, different database)
# Format: postgresql+asyncpg://user:password@host:port/database
TEST_DATABASE_URL = settings.DATABASE_URL.rsplit("/", 1)[0] + "/claimmatrix_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create session factory
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db(test_engine):
    """Clean up database after each test."""
    yield

    # Truncate all tables after each test
    async with test_engine.begin() as conn:
        await conn.execute(sa.text("TRUNCATE TABLE users CASCADE"))


@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend."""
    return "asyncio"


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with database session override."""
    from app.main import app
    from app.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture
def auth_token(test_user: User) -> str:
    """Create an authentication token for test user."""
    return create_access_token(data={"sub": str(test_user.id), "email": test_user.email})


@pytest.fixture
def auth_token2(test_user2: User) -> str:
    """Create an authentication token for second test user."""
    return create_access_token(data={"sub": str(test_user2.id), "email": test_user2.email})


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Create authorization headers with Bearer token for test user."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def auth_headers2(auth_token2: str) -> dict:
    """Create authorization headers for second test user."""
    return {"Authorization": f"Bearer {auth_token2}"}


# ============================================================================
# Test Data Fixtures
# ============================================================================
