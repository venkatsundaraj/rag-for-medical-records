import asyncpg
from app.config import settings

_pool: asyncpg.Pool | None = None

async def create_pool()->asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=5, max_size=20, command_timeout=60)
    return _pool

async def get_pool()->asyncpg.Pool:
    global _pool
    if _pool in None:
        raise RuntimeError("db is not initialized yet")
    return _pool

async def close_pool(pool:asyncpg.Pool | None = None)->None:
    global _pool
    target = _pool or pool
    if target:
        await target.close()
    _pool = None
