import asyncio
import json
import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

from app.services.websocket_manager import get_websocket_manager


async def listen(
    redis_url: str,
    channel: str,
):
    """
    Asynchronously listens to a Redis channel and broadcasts received messages to WebSocket clients.
    Args:
        redis_url (str): The URL of the Redis server to connect to.
        channel (str): The name of the Redis channel to subscribe to.
    Behavior:
        - Subscribes to the specified Redis channel.
        - Listens for incoming messages on the channel.
        - For each message of type "message", parses the JSON data and broadcasts it to the appropriate WebSocket room using the WebSocket manager.
    Raises:
        Any exceptions raised by aioredis or JSON parsing will propagate.
    """
    redis = aioredis.from_url(redis_url, decode_responses=True)
    pubsub: PubSub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await get_websocket_manager().broadcast(
                    data["room"],
                    data["payload"],
                )
    except asyncio.CancelledError:
        # Handle cancellation gracefully
        await pubsub.unsubscribe(channel)
        await redis.close()
        raise
