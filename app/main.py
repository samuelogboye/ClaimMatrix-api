"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
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
from app.exceptions import ClaimMatrixException
from app.exception_handlers import (
    claimmatrix_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler,
)

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

# Register global exception handlers
app.add_exception_handler(ClaimMatrixException, claimmatrix_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

logger.info("Global exception handlers registered")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request/response logging middleware
app.add_middleware(LoggingMiddleware)


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint with database connectivity check.

    Args:
        db: Database session

    Returns:
        Health status including database connectivity
    """
    health_status = {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {
            "connected": False,
            "status": "unknown"
        }
    }

    # Check database connectivity
    try:
        # Execute a simple query to verify database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        health_status["database"]["connected"] = True
        health_status["database"]["status"] = "healthy"

        logger.debug("Health check passed - database connection healthy")

        return JSONResponse(
            status_code=200,
            content=health_status
        )
    except Exception as e:
        # Database connection failed
        health_status["status"] = "unhealthy"
        health_status["database"]["connected"] = False
        health_status["database"]["status"] = f"error: {str(e)}"

        logger.error(
            f"Health check failed - database connection error: {str(e)}",
            exc_info=True
        )

        return JSONResponse(
            status_code=503,
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
    )
