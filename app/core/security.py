from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import TokenError

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using the application's password context.

    Args:
        password (str): The plain-text password to be hashed.

    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifies that a plain text password matches its hashed version.

    Args:
        plain (str): The plain text password to verify.
        hashed (str): The hashed password to compare against.

    Returns:
        bool: True if the plain password matches the hashed password, False otherwise.
    """
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any], expires_delta: timedelta = None) -> str:
    """
    Generates a JSON Web Token (JWT) access token.

    Args:
        data (dict[str, Any]): The payload data to encode into the token.
        expires_delta (timedelta, optional): The time duration until the token expires.
            If not provided, a default expiration time from settings is used.

    Returns:
        str: The encoded JWT access token as a string.
    """
    to_encode = data.copy()
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes a JWT access token and returns its payload.

    Args:
        token (str): The JWT access token to decode.

    Returns:
        dict[str, Any]: The decoded payload of the token.

    Raises:
        TokenError: If the token is expired or invalid.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenError("Token has expired")
    except jwt.InvalidTokenError:
        raise TokenError("Invalid token")
