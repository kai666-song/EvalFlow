from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
import app.main as main_module

app = main_module.app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_session() -> AsyncIterator[AsyncSession]:
    """向接口提供测试数据库会话。"""

    async with TestSessionFactory() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    monkeypatch,
) -> AsyncIterator[AsyncClient]:
    """为每个测试创建独立数据库和HTTP客户端。"""

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    app.dependency_overrides[get_session] = override_get_session

    monkeypatch.setattr(
        main_module,
        "AsyncSessionFactory",
        TestSessionFactory,
    )

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_session, None)

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session(
    client: AsyncClient,
) -> AsyncIterator[AsyncSession]:
    """提供用于断言数据库状态的测试会话。"""

    async with TestSessionFactory() as session:
        yield session