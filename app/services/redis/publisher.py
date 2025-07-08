from typing import Any, Dict
import redis.asyncio as aioredis
import json

from app.core.config import get_settings

settings = get_settings()
REDIS_URL = settings.REDIS_URL
CHANNEL_NAME = settings.REDIS_CHANNEL


async def publish_message(room: str, payload: Dict[str, Any]) -> None:
    """
    Publishes a message to a Redis channel.

    Args:
        room (str): The room identifier to which the message belongs.
        payload (dict): The message payload to be published.
    """
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    message = {
        "room": room,
        "payload": payload,
    }
    await redis.publish(CHANNEL_NAME, json.dumps(message))
