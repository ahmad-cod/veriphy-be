from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from asgi_correlation_id import CorrelationIdMiddleware
import structlog
from sqlalchemy import text

from src.core.config import settings
from src.core.exceptions import (
    VeriphyException,
    veriphy_exception_handler,
    global_exception_handler,
)
from src.infrastructure.database import engine
from src.infrastructure.redis import init_redis, close_redis
from src.api.v1.routers import merchant_router, verification_router

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Veriphy API...", env=settings.ENVIRONMENT)
    try:
        # Ping Database without opening a transaction
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection verified.")

        await init_redis()
    except Exception as e:
        logger.error("Failed to connect to infrastructure on startup", error=str(e))
        raise RuntimeError("Infrastructure connection failed") from e
        
    yield # App runs here
    
    logger.info("Shutting down Veriphy API...")
    await close_redis()
    await engine.dispose()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan
    )

    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["*"] if settings.ENVIRONMENT == "local" else ["api.veriphy.ng", "staging-api.veriphy.ng"]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Pure ASGI middleware for correlation IDs
    app.add_middleware(CorrelationIdMiddleware)

    async def _veriphy_exception_handler(request: Request, exc: Exception):
        return await veriphy_exception_handler(request, exc)  # type: ignore[arg-type]

    app.add_exception_handler(VeriphyException, _veriphy_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(merchant_router)
    app.include_router(verification_router)

    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "ok"}

    return app

app = create_app()