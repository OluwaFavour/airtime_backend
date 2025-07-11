import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from httpx import HTTPStatusError, RequestError

from app.api.v1 import auth, wallet, websocket
from app.core.config import app_logger, get_settings
from app.db.init_db import init_indexes
from app.db.config import database
from app.exceptions.handlers import (
    bank_verification_error_handler,
    credential_error_handler,
    database_error_handler,
    httpx_error_handler,
    inactive_object_error_handler,
    object_already_exists_error_handler,
    object_not_found_error_handler,
    payment_failed_error_handler,
    token_error_handler,
    transaction_error_handler,
    wallet_error_handler,
)
from app.exceptions.types import (
    BankVerificationError,
    CredentialError,
    DatabaseError,
    InactiveObjectError,
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    PaymentFailedError,
    TokenError,
    TransactionError,
    WalletError,
)
from app.services.async_client import async_request_client
from app.services.redis import listener as redis_listener


settings = get_settings()
REDIS_URL = settings.REDIS_URL
CHANNEL_NAME = settings.REDIS_CHANNEL


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for the FastAPI application.

    This asynchronous function is used to perform startup and shutdown tasks for the application.
    It initializes necessary database indexes before the application starts serving requests.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control is yielded back to FastAPI after initialization.
    """
    app_logger.info("Starting Airtime Backend API...")
    # Initialize database indexes
    app_logger.info("Initializing database indexes...")
    await init_indexes(database)
    app_logger.info("Database indexes initialized successfully.")
    # Start the Redis listener for WebSocket messages
    app_logger.info("Starting Redis listener for WebSocket messages...")
    app.state.redis_listener_task = asyncio.create_task(
        redis_listener.listen(REDIS_URL, CHANNEL_NAME)
    )

    try:
        yield
    finally:
        app_logger.info("Shutting down Airtime Backend API...")
        # Cancel the Redis listener task
        task = app.state.redis_listener_task
        if task:
            app_logger.info("Cancelling Redis listener task...")
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            app_logger.info("Redis listener task cancelled successfully.")

        # Close the async HTTP client
        app_logger.info("Closing async HTTP client...")
        await async_request_client.close()


app = FastAPI(
    title="Airtime Backend",
    description="Airtime backend API for managing users, authentication, and more.",
    version="1.0.0",
    root_path="/api/v1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Include exception handlers
app.add_exception_handler(
    CredentialError,
    credential_error_handler,
)
app.add_exception_handler(
    TokenError,
    token_error_handler,
)
app.add_exception_handler(
    InactiveObjectError,
    inactive_object_error_handler,
)
app.add_exception_handler(
    ObjectNotFoundError,
    object_not_found_error_handler,
)
app.add_exception_handler(
    ObjectAlreadyExistsError,
    object_already_exists_error_handler,
)
app.add_exception_handler(
    DatabaseError,
    database_error_handler,
)
app.add_exception_handler(WalletError, wallet_error_handler)
app.add_exception_handler(PaymentFailedError, payment_failed_error_handler)
app.add_exception_handler(RequestError, httpx_error_handler)
app.add_exception_handler(HTTPStatusError, httpx_error_handler)
app.add_exception_handler(BankVerificationError, bank_verification_error_handler)
app.add_exception_handler(
    TransactionError,
    transaction_error_handler,
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/")
async def root(request: Request):
    base_url = request.base_url._url.rstrip("/")
    return {
        "message": "Welcome to the Airtime Backend API",
        "documentations": {
            "swagger": f"{base_url}/docs",
            "redoc": f"{base_url}/redoc",
        },
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify if the API is running.
    """
    return {"status": "ok", "message": "Airtime Backend API is running."}


@app.get("/ping-rabbitmq")
async def ping_rabbitmq():
    """
    Endpoint to ping RabbitMQ to ensure the connection is active.
    This is a placeholder for any RabbitMQ-related functionality.
    """
    # TODO: Placeholder for RabbitMQ ping logic
    return {"status": "ok", "message": "RabbitMQ connection is active."}
