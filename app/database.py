from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import(
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./evalflow.db"

class Base(DeclarativeBase):
    """所有数据ORM模型的基类。"""

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)


AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, 
)

async def get_session() -> AsyncIterator[AsyncSession]:
    """为一次请求提供独立的数据库会话。"""


    async with AsyncSessionFactory() as session:
        yield session

async def init_database() -> None:
    """创建当前尚不存在的数据库表。"""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        