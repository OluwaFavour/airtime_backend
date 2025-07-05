from fastapi import FastAPI, Request

from app.api.v1 import auth
from app.exceptions.handlers import (
    credential_error_handler,
    database_error_handler,
    inactive_object_error_handler,
    object_already_exists_error_handler,
    object_not_found_error_handler,
    token_error_handler,
)
from app.exceptions.types import (
    CredentialError,
    DatabaseError,
    InactiveObjectError,
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    TokenError,
)


app = FastAPI(
    title="Airtime Backend",
    description="Airtime backend API for managing users, authentication, and more.",
    version="1.0.0",
    root_path="/api/v1",
    docs_url="/docs",
    redoc_url="/redoc",
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

app.include_router(auth.router, prefix="/auth", tags=["auth"])


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
