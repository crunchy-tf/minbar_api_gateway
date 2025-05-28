# api_gateway_service/app/db_connector.py
import asyncpg
from typing import Optional, List, Dict, Any
from loguru import logger
from fastapi import HTTPException # <<< --- THIS IS THE CRUCIAL IMPORT --- <<<
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
        # Allow the error to propagate to the lifespan manager in main.py
        # which will then decide whether to halt startup.
        raise ConnectionError(f"API Gateway: Could not connect to TimescaleDB during pool creation: {e}") from e

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
        try:
            await connect_db()
        except ConnectionError as ce: # Catch the specific error from connect_db
            logger.error(f"API Gateway: Failed to (re)initialize pool in get_pool: {ce}")
            raise # Re-raise to signal unavailability
            
    if _pool is None: 
        # This should ideally be caught by the exception above from connect_db if it fails
        raise ConnectionError("API Gateway: TimescaleDB pool remains unavailable after (re)initialization attempt.")
    return _pool

async def fetch_data(query: str, *args) -> List[asyncpg.Record]:
    try:
        pool = await get_pool() # This can raise ConnectionError if pool is not available
    except ConnectionError as e:
        logger.error(f"API Gateway: Database connection error before fetching data: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.") from e

    try:
        async with pool.acquire() as conn:
            logger.debug(f"Executing query: {query} with args: {args}")
            return await conn.fetch(query, *args)
    except asyncpg.PostgresError as e: # Catch specific database operational errors
        logger.error(f"API Gateway: Database query error: {e}\nQuery: {query}\nArgs: {args}", exc_info=True)
        # Raise HTTPException so FastAPI handles it and returns a proper 500
        raise HTTPException(status_code=500, detail=f"Database query error occurred: {type(e).__name__}.") from e
    except Exception as e: # Catch any other unexpected errors during the fetch itself
        logger.error(f"API Gateway: Unexpected error during DB fetch operation: {e}\nQuery: {query}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error during database operation.") from e