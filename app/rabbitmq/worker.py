# app/rabbitmq/worker.py
import asyncio
import json
import aio_pika

from app.services.payment_gateway import get_flutterwave_client
from app.core.config import get_settings, rabbitmq_logger

settings = get_settings()


async def handle_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process(ignore_processed=True):
        try:
            payload = json.loads(message.body.decode())
            rabbitmq_logger.info(f"Received message: {payload}")
            await get_flutterwave_client().process_webhook(payload)
        except Exception as e:
            rabbitmq_logger.error(f"Error processing message: {e}")


async def consume_payment_events():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    queue = await channel.declare_queue("wallet.events", durable=True)

    await queue.consume(handle_message)
    rabbitmq_logger.info(" [*] Waiting for wallet events. To exit press CTRL+C")

    try:
        await asyncio.Future()  # Run forever
    finally:
        await connection.close()
        rabbitmq_logger.info("Connection closed.")


if __name__ == "__main__":
    asyncio.run(consume_payment_events())
