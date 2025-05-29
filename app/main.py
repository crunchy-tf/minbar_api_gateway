# api_gateway_service/app/main.py

from fastapi import FastAPI, Request, Depends, HTTPException, status # Added status
from fastapi.responses import JSONResponse, Response
from loguru import logger
import sys
import time
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.db_connector import connect_db, close_db, get_pool
from app.security import get_current_username
from app.rate_limiter import rate_limit_dependency
from app.routers import signals_router, keywords_router, analysis_router
from app.external_services import check_keyword_manager_health # MODIFIED: Import KM health check

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
    db_connected = False
    km_connected = False

    # 1. Connect to Database
    try:
        await connect_db()
        logger.info(f"{settings.SERVICE_NAME} connected to database.")
        db_connected = True
    except Exception as e:
        logger.critical(f"{settings.SERVICE_NAME} failed to connect to database during startup: {e}", exc_info=True)

    # 2. Check Keyword Manager Health (Optional Startup Blocker)
    # If KM is absolutely critical for startup, you might want to make this check mandatory.
    # For now, we'll log its status but not necessarily prevent startup if it's down,
    # as some Gateway endpoints might not depend on it.
    # The /health endpoint will reflect its status.
    try:
        km_healthy = await check_keyword_manager_health()
        if km_healthy:
            logger.info("Keyword Manager health check successful during startup.")
            km_connected = True
        else:
            logger.warning("Keyword Manager health check failed during startup. Service may have limited functionality.")
    except Exception as e:
        logger.error(f"Error checking Keyword Manager health during startup: {e}", exc_info=True)

    # Decide if service should start based on critical dependencies
    if not db_connected: # Make DB connection mandatory
         # If you made km_connected mandatory too, add 'and not km_connected'
        logger.critical("Critical dependency (Database) failed. API Gateway will not start properly.")
        # To actually prevent FastAPI from serving requests if critical dependencies are down,
        # you can raise a RuntimeError here. This will stop Uvicorn.
        raise RuntimeError("API Gateway startup failed due to critical dependency failure.")


    logger.info(f"{settings.SERVICE_NAME} startup sequence complete (DB: {'OK' if db_connected else 'FAIL'}, KM: {'OK' if km_connected else 'FAIL'}).")
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

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return Response(status_code=204)

app.include_router(signals_router.router)
app.include_router(keywords_router.router)
app.include_router(analysis_router.router)

@app.get("/", tags=["Root"])
async def read_root(username: str = Depends(get_current_username)):
    return {"message": f"Welcome to {settings.SERVICE_NAME}, {username}! All systems operational."}

@app.get("/health", tags=["Health"])
async def health_check():
    db_ok = False
    db_status = "error: unknown"
    km_ok = False
    km_status = "error: unknown"

    # Check Database
    try:
        pool = await get_pool() # This already tries to connect if pool is None
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
        db_status = "connected"
    except Exception as e:
        logger.warning(f"Health check: Database connection error: {e}")
        db_status = f"error: {type(e).__name__}"

    # Check Keyword Manager
    try:
        km_ok = await check_keyword_manager_health()
        km_status = "connected" if km_ok else "unreachable_or_unhealthy"
    except Exception as e: # Should be caught by check_keyword_manager_health, but defensive
        logger.warning(f"Health check: Error during Keyword Manager check: {e}")
        km_status = f"error_checking: {type(e).__name__}"

    # Determine overall service status
    # For the service to be "ok", both DB and KM must be ok. Adjust if KM is optional.
    service_is_fully_healthy = db_ok and km_ok
    service_status = "ok" if service_is_fully_healthy else "degraded" # or "error" if KM is critical
    http_status_code = status.HTTP_200_OK if service_is_fully_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    if not service_is_fully_healthy:
        logger.warning(f"Health check failed or degraded: DB='{db_status}', KM='{km_status}'")


    return JSONResponse(
        status_code=http_status_code,
        content={
            "status": service_status,
            "service_name": settings.SERVICE_NAME,
            "dependencies": {
                "database": db_status,
                "keyword_manager": km_status
            }
        }
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