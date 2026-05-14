import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
import structlog
from redis.asyncio import Redis

from src.infrastructure.websockets import ws_manager
from src.infrastructure.redis import get_redis

router = APIRouter(tags=["Realtime"])
logger = structlog.get_logger()

async def verify_ws_token(token: str) -> str:
    # In production: Exchange short-lived WS ticket here instead of static JWT
    if not token:
        raise ValueError("Missing token")
    return "123e4567-e89b-12d3-a456-426614174000"

@router.websocket("/ws/verify")
async def verification_socket(
    websocket: WebSocket,
    token: str = Query(...),
    redis: Redis = Depends(get_redis)
):
    try:
        merchant_id = await verify_ws_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid authentication")
        return

    await ws_manager.connect(websocket, merchant_id)
    channel_name = f"verdict:{merchant_id}"
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(channel_name)
        logger.info("Subscribed to Redis channel", channel=channel_name)

        # Red Team Fix: Efficient async generator instead of busy-wait
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    await ws_manager.push_to_client(merchant_id, payload)
                except Exception as e:
                    logger.error("Failed to parse broadcast", error=str(e), merchant_id=merchant_id)

    except WebSocketDisconnect:
        logger.info("Client disconnected normally", merchant_id=merchant_id)
    except Exception as e:
        logger.error("WebSocket connection error", merchant_id=merchant_id, error=str(e))
    finally:
        # Red Team Fix: Bulletproof cleanup to prevent Redis connection leaks
        try:
            await pubsub.unsubscribe(channel_name)
            await pubsub.aclose()
        except Exception as e:
            logger.warning("Error closing pubsub", error=str(e))
        ws_manager.disconnect(merchant_id)