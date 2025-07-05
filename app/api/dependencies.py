from tokenize import TokenError
from fastapi import Depends
from typing import Annotated, AsyncGenerator

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.read_concern import ReadConcern

from app.exceptions.types import CredentialError, InactiveObjectError
from app.core.security import decode_access_token, get_authentication_token
from app.db.models.user import UserModel
from app.db.config import client, database
from app.db.crud.user import UserDB

user_collection = database.get_collection("users")
user_db = UserDB(user_collection)


def get_user_db() -> UserDB:
    """
    Dependency to get an instance of UserDB for database operations related to users.

    Returns:
        UserDB: An instance of UserDB initialized with the user collection.
    """
    return user_db


async def get_session() -> AsyncGenerator[AsyncClientSession, None]:
    """
    Dependency to get an active session for database operations.

    Returns:
        AsyncSession: An instance of AsyncSession for database operations.
    """
    async with client.start_session() as session:
        yield session


async def get_current_user(
    token: Annotated[str, Depends(get_authentication_token)],
) -> UserModel:
    """
    Dependency to get the current user based on the provided JWT token.

    Args:
        token (str): The JWT token provided by the user.

    Returns:
        UserModel: The authenticated user model.

    Raises:
        CredentialError: If the token is invalid or the user cannot be found.
        TokenError: If there is an error decoding the token.
    """
    try:
        payload = decode_access_token(token)
        user = await user_db.get_by_id(payload["sub"])
        if not user:
            raise CredentialError("User not found")
        return user
    except TokenError:
        raise
    except CredentialError:
        raise


async def get_current_active_user(
    current_user: Annotated[UserModel, Depends(get_current_user)],
) -> UserModel:
    if not current_user.is_active:
        raise InactiveObjectError("User is inactive")
    return current_user
