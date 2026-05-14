import json
from uuid import UUID
from datetime import datetime, timezone
from fastapi import WebSocket
import structlog

# Import the global redis connection pool from Phase 4
from src.infrastructure.redis import redis_client

logger = structlog.get_logger()

class ConnectionManager:
    def __init__(self):
        # Maps merchant_id to their active WebSocket connection on THIS Uvicorn worker
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, merchant_id: str):
        await websocket.accept()
        self.active_connections[merchant_id] = websocket
        logger.info("WebSocket connected", merchant_id=merchant_id)

    def disconnect(self, merchant_id: str):
        if merchant_id in self.active_connections:
            del self.active_connections[merchant_id]
            logger.info("WebSocket disconnected", merchant_id=merchant_id)

    async def push_to_client(self, merchant_id: str, payload: dict):
        """Pushes data directly to the client if they are connected to this worker."""
        ws = self.active_connections.get(merchant_id)
        if ws:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.error("Failed to send WS message", merchant_id=merchant_id, error=str(e))
                self.disconnect(merchant_id)

# Singleton instance for the local FastAPI worker
ws_manager = ConnectionManager()

async def broadcast_verdict(merchant_id: UUID, job_id: UUID, state: str, reason: str | None = None):
    """
    Called by the CELERY WORKER. 
    Publishes the verdict to the Redis channel specific to this merchant.
    Designed as 'fire-and-forget' so a Redis blip doesn't crash the Celery task.
    """
    try:
        if redis_client is None:
            raise RuntimeError("Redis client not initialized")
            
        channel = f"verdict:{merchant_id}"
        payload = json.dumps({
            "type": "VERDICT_UPDATE",
            "job_id": str(job_id),
            "state": state,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        await redis_client.publish(channel, payload)
        logger.info("Broadcasted verdict to Redis", channel=channel, job_id=str(job_id))
    except Exception as e:
        logger.error("Failed to broadcast verdict", error=str(e), job_id=str(job_id))
        # Client will automatically fallback to REST polling via GET /verify/{job_id}