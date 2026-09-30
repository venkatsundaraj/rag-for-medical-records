from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from collections.abc import AsyncGenerator
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'),
    pool_size=5,
    max_overflow=15
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db()->AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session



