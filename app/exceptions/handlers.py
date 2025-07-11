from typing import Union
from httpx import RequestError, HTTPStatusError
from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_wallet_db
from app.core.config import request_logger
from app.exceptions.types import (
    BankVerificationError,
    CredentialError,
    DatabaseError,
    InactiveObjectError,
    ObjectNotFoundError,
    PaymentFailedError,
    PaymentGatewayError,
    TokenError,
    TransactionError,
    WalletAwareError,
    WalletError,
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
        status_code=exc.status_code,
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


async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """
    Handles DatabaseError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (DatabaseError): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 500.
    """
    request_logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


async def wallet_error_handler(request: Request, exc: WalletError) -> JSONResponse:
    """
    Handles WalletError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (WalletError): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 500.
    """
    request_logger.error(f"Wallet error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


async def httpx_error_handler(
    request: Request, exc: Union[RequestError, HTTPStatusError]
) -> JSONResponse:
    """
    Handles HTTPX errors and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (Union[RequestError, HTTPStatusError]): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 500.
    """
    request_logger.error(f"HTTPX request error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An error occurred while making an HTTP request.",
            "error": str(exc),
        },
    )


async def payment_failed_error_handler(
    request: Request, exc: PaymentFailedError
) -> JSONResponse:
    """
    Handles PaymentFailedError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (PaymentFailedError): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 402.
    """
    request_logger.error(f"Payment failed error: {str(exc)}")
    # TODO: Use celery to send a notification to the user about the payment failure
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={"detail": str(exc)},
    )


async def bank_verification_error_handler(
    request: Request, exc: BankVerificationError
) -> JSONResponse:
    """
    Handles BankVerificationError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (BankVerificationError): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 400.
    """
    request_logger.error(f"Bank verification error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def transaction_error_handler(
    request: Request, exc: TransactionError
) -> JSONResponse:
    """
    Handles TransactionError exceptions and returns a JSON response with the error message.

    Args:
        request (Request): The incoming request object.
        exc (TransactionError): The exception instance containing the error message.

    Returns:
        JSONResponse: A JSON response with the error message and status code 500.
    """
    request_logger.error(f"Transaction error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_417_EXPECTATION_FAILED,
        content={"detail": f"Transaction error: {str(exc)}"},
    )


async def wallet_aware_error_handler(
    request: Request, exc: WalletAwareError
) -> JSONResponse:
    if exc.unlock_wallet:
        wallet_db = get_wallet_db()
        await wallet_db.toggle_wallet_lock(exc.user_id, lock=False)
    request_logger.error(f"Wallet aware error: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message},
    )
