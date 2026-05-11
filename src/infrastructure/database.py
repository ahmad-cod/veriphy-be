from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "local"), # Log SQL queries in local dev
    pool_pre_ping=True, # Check if connections are alive before using
    pool_size=20,
    max_overflow=10,
    pool_timeout=30, # Wait up to 30 seconds for a connection from the pool
    pool_recycle=1800, # Recycle connections after 30 mins
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency for database sessions.
    Yields a session and automatically closes it when the request completes.
    """
    async with AsyncSessionLocal() as session:
        yield session

        # Context manager handles rollback on exception and auto-close