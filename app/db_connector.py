import asyncpg
from typing import Optional, List, Dict, Any
from loguru import logger
from app.config import settings

_pool: Optional[asyncpg.Pool] = None

async def connect_db():
    global _pool
    if _pool and not getattr(_pool, '_closed', True):
        logger.debug("API Gateway: TimescaleDB connection pool already established.")
        return
    logger.info(f"API Gateway: Connecting to TimescaleDB using DSN: {settings.timescaledb_dsn_asyncpg}")
    try:
        _pool = await asyncpg.create_pool(dsn=settings.timescaledb_dsn_asyncpg, min_size=1, max_size=5)
        logger.success("API Gateway: TimescaleDB connection pool established.")
    except Exception as e:
        logger.critical(f"API Gateway: Failed to connect to TimescaleDB: {e}", exc_info=True)
        _pool = None
        raise ConnectionError("API Gateway: Could not connect to TimescaleDB") from e

async def close_db():
    global _pool
    if _pool:
        logger.info("API Gateway: Closing TimescaleDB connection pool.")
        await _pool.close()
        _pool = None
        logger.success("API Gateway: TimescaleDB connection pool closed.")

async def get_pool() -> asyncpg.Pool:
    if _pool is None or getattr(_pool, '_closed', True):
        logger.warning("API Gateway: TimescaleDB pool is None or closed. Attempting to (re)initialize...")
        await connect_db()
    if _pool is None: 
        raise ConnectionError("API Gateway: TimescaleDB pool unavailable after (re)initialization attempt.")
    return _pool

async def fetch_data(query: str, *args) -> List[asyncpg.Record]:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            logger.debug(f"Executing query: {query} with args: {args}")
            return await conn.fetch(query, *args)
    except asyncpg.PostgresError as e:
        logger.error(f"API Gateway: Database query error: {e}\nQuery: {query}\nArgs: {args}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database query error occurred.") from e
    except Exception as e:
        logger.error(f"API Gateway: Unexpected error during DB fetch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected database error.") from e