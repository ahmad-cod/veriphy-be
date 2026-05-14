from typing import AsyncGenerator
from redis.asyncio.client import Redis
from redis.asyncio import from_url
from src.core.config import settings
import structlog

logger = structlog.get_logger()

# Global variable to hold the initialized Redis client pool
redis_client: Redis | None = None

async def init_redis() -> None:
    """
    Initializes the async Redis client with a connection pool.
    Call this during the FastAPI startup event.
    """
    global redis_client
    logger.info("Initializing Redis connection pool...")
    
    try:
        client: Redis = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True, # Automatically decodes byte responses to strings
            max_connections=100,   # Set a ceiling to prevent overwhelming the Redis server
            socket_timeout=5.0,    # Fail fast if Redis is hanging
        )
        
        # Ping the server to ensure the connection is actually alive
        await client.ping()

        redis_client = client
        logger.info("Redis connection pool established successfully.")

    except Exception as e:
        logger.warning("Failed to connect to Redis, running without Redis", error=str(e))
        redis_client = None

async def close_redis() -> None:
    """
    Gracefully closes the connection pool.
    Call this during the FastAPI shutdown event.
    """
    global redis_client
    if redis_client:
        logger.info("Closing Redis connection pool...")
        await redis_client.aclose()
        logger.info("Redis connection pool closed.")

async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    FastAPI Dependency to inject the Redis client into routers and services.
    
    Note: We do not open/close a connection here. We yield the global client,
    which internally manages checking out and returning connections to the pool
    whenever an awaitable command (like `await redis.incr()`) is called.
    """
    if redis_client is None:
        logger.error("Attempted to get Redis client before initialization.")
        raise RuntimeError("Redis client is not initialized")
    
    yield redis_client