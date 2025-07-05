from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.config import request_logger
from app.exceptions.types import (
    CredentialError,
    InactiveObjectError,
    ObjectNotFoundError,
    TokenError,
)


async def credential_error_handler(
    request: Request, exc: CredentialError
) -> JSONResponse:
    """
    Handles CredentialError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (CredentialError): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 401.
    """
    request_logger.error(f"Credential error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
    )


async def token_error_handler(request: Request, exc: TokenError) -> JSONResponse:
    """
    Handles TokenError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (TokenError): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 401.
    """
    request_logger.error(f"Token error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
    )


async def inactive_object_error_handler(
    request: Request, exc: InactiveObjectError
) -> JSONResponse:
    """
    Handles InactiveObjectError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (Exception): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 404.
    """
    request_logger.error(f"Inactive object error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


async def object_not_found_error_handler(
    request: Request, exc: ObjectNotFoundError
) -> JSONResponse:
    """
    Handles ObjectNotFoundError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (ObjectNotFoundError): The exception instance containing the error message.
    Returns:
        JSONResponse: A JSON response with the error message and status code 404.
    """
    request_logger.error(f"Object not found error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def object_already_exists_error_handler(
    request: Request, exc: ObjectNotFoundError
) -> JSONResponse:
    """
    Handles ObjectAlreadyExistsError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (ObjectNotFoundError): The exception instance containing the error message.
    Returns:
        JSONResponse: A JSON response with the error message and status code 409.
    """
    request_logger.error(f"Object already exists error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handles DatabaseError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (Exception): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 500.
    """
    request_logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )
