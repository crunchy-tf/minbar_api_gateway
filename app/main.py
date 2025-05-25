from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
import sys
import time
from contextlib import asynccontextmanager

from app.config import settings
from app.db_connector import connect_db, close_db, get_pool
from app.security import get_current_username
from app.rate_limiter import rate_limit_dependency
from app.routers import signals_router, keywords_router, analysis_router

logger.remove()
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(sys.stderr, level=settings.LOG_LEVEL.upper(), format=log_format)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Attempting to start {settings.SERVICE_NAME}...")
    try:
        await connect_db()
        logger.info(f"{settings.SERVICE_NAME} connected to database.")
    except Exception as e:
        logger.critical(f"{settings.SERVICE_NAME} failed to connect to database during startup: {e}", exc_info=True)
        # Depending on policy, you might want the app to not start if DB is down.
        # For now, it will start but DB calls will fail.
        # To prevent startup, re-raise or sys.exit()
        # raise RuntimeError("Database connection failed, cannot start service.") from e

    logger.info(f"{settings.SERVICE_NAME} startup sequence complete.")
    yield
    logger.info(f"Attempting to shut down {settings.SERVICE_NAME}...")
    await close_db()
    logger.info(f"{settings.SERVICE_NAME} shutdown complete.")

app = FastAPI(
    title=settings.SERVICE_NAME,
    description="API Gateway for the Minbar Public Health Monitoring Platform.",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(rate_limit_dependency)] 
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

app.include_router(signals_router.router)
app.include_router(keywords_router.router)
app.include_router(analysis_router.router)

@app.get("/", tags=["Root"])
async def read_root(username: str = Depends(get_current_username)):
    return {"message": f"Welcome to {settings.SERVICE_NAME}, {username}! All systems operational."}

@app.get("/health", tags=["Health"])
async def health_check():
    db_ok = False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
        db_status = "connected"
    except Exception as e:
        logger.warning(f"Health check DB connection error: {e}")
        db_status = f"error: {type(e).__name__}"
    
    service_status = "ok" if db_ok else "error"
    http_status = 200 if db_ok else 503

    return JSONResponse(
        status_code=http_status,
        content={"status": service_status, "service_name": settings.SERVICE_NAME, "database": db_status}
    )

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting {settings.SERVICE_NAME} locally on host 0.0.0.0 port {settings.SERVICE_PORT}")
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=settings.SERVICE_PORT, 
        log_level=settings.LOG_LEVEL.lower(), 
        reload=True 
    )