"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from app.config import settings
from app.database import init_db, close_db, get_db
from app.api import users, auth, claims
from app.middleware import LoggingMiddleware
from app.utils.logging_config import setup_logging, get_logger
from app.utils.rate_limit import limiter
from app.exceptions import ClaimMatrixException
from app.exception_handlers import (
    claimmatrix_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler,
)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Note: Database tables should be created via Alembic migrations
    # init_db() is only for development/testing
    # await init_db()

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="An AI-powered medical claims audit engine for self-insured employers and health plans",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add rate limiter state
app.state.limiter = limiter

# Register global exception handlers
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(ClaimMatrixException, claimmatrix_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

logger.info("Global exception handlers registered")
if settings.RATE_LIMIT_ENABLED:
    logger.info(f"Rate limiting enabled - Default: {settings.RATE_LIMIT_DEFAULT}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression for responses > 1KB (improves response times for large payloads)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add request/response logging middleware
app.add_middleware(LoggingMiddleware)


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Comprehensive health check endpoint.

    Checks:
    - Database connectivity
    - Redis connectivity
    - Celery worker availability

    Args:
        db: Database session

    Returns:
        Health status including all system components
    """
    import redis
    from celery import Celery

    health_status = {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": {
            "connected": False,
            "status": "unknown"
        },
        "redis": {
            "connected": False,
            "status": "unknown"
        },
        "celery": {
            "workers_available": False,
            "status": "unknown"
        }
    }

    # Check database connectivity
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        health_status["database"]["connected"] = True
        health_status["database"]["status"] = "healthy"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"]["connected"] = False
        health_status["database"]["status"] = f"error: {str(e)}"
        logger.error(f"Health check - database error: {str(e)}")

    # Check Redis connectivity
    try:
        redis_client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        redis_client.ping()
        health_status["redis"]["connected"] = True
        health_status["redis"]["status"] = "healthy"
        redis_client.close()
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["redis"]["connected"] = False
        health_status["redis"]["status"] = f"error: {str(e)}"
        logger.warning(f"Health check - Redis error: {str(e)}")

    # Check Celery workers
    try:
        from app.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=2.0)
        active_workers = inspect.active()
        if active_workers and len(active_workers) > 0:
            health_status["celery"]["workers_available"] = True
            health_status["celery"]["status"] = "healthy"
            health_status["celery"]["worker_count"] = len(active_workers)
        else:
            health_status["status"] = "degraded"
            health_status["celery"]["workers_available"] = False
            health_status["celery"]["status"] = "no workers available"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["celery"]["workers_available"] = False
        health_status["celery"]["status"] = f"error: {str(e)}"
        logger.warning(f"Health check - Celery error: {str(e)}")

    # Determine HTTP status code
    status_code = 200
    if health_status["status"] == "unhealthy":
        status_code = 503
    elif health_status["status"] == "degraded":
        status_code = 200  # Still return 200 for degraded (database works)

    logger.debug(f"Health check completed - status: {health_status['status']}")

    return JSONResponse(
        status_code=status_code,
        content=health_status
    )


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint.

    Returns:
        Welcome message
    """
    return JSONResponse(
        content={
            "message": f"Welcome to {settings.APP_NAME} API",
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }
    )


# Include routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(claims.router, prefix=settings.API_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        timeout_keep_alive=5,  # Keep-alive timeout
        timeout_graceful_shutdown=30,  # Graceful shutdown timeout
        limit_concurrency=1000,  # Maximum concurrent connections
        limit_max_requests=10000,  # Restart worker after N requests (prevents memory leaks)
    )
