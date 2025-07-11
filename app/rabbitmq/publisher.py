# app/rabbitmq/publisher.py
import json
from typing import Any, Dict
import aio_pika
from app.core.config import get_settings

settings = get_settings()


async def publish_flutter_event(event: Dict[str, Any]) -> None:
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await channel.declare_queue(name="wallet.events", durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(event).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="wallet.events",
        )
