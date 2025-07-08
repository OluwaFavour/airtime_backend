from contextlib import asynccontextmanager
from tokenize import TokenError
from fastapi import Depends
from typing import Annotated, AsyncGenerator

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.read_concern import ReadConcern

from app.db.config import client
from app.core.security import decode_access_token, get_authentication_token
from app.db.crud.transactions import TransactionDB
from app.db.crud.user import UserDB
from app.db.crud.wallet import WalletDB
from app.db.models.wallet import wallet_collection, transaction_collection
from app.db.models.user import UserModel, user_collection
from app.exceptions.types import CredentialError, InactiveObjectError

user_db = UserDB(user_collection)
wallet_db = WalletDB(wallet_collection)
transaction_db = TransactionDB(transaction_collection)


def get_user_db() -> UserDB:
    """
    Dependency to get an instance of UserDB for database operations related to users.

    Returns:
        UserDB: An instance of UserDB initialized with the user collection.
    """
    return user_db


def get_wallet_db() -> WalletDB:
    """
    Dependency to get an instance of WalletDB for database operations related to wallets.

    Returns:
        WalletDB: An instance of WalletDB initialized with the wallet collection.
    """
    return wallet_db


def get_transaction_db() -> TransactionDB:
    """
    Dependency to get an instance of TransactionDB for database operations related to transactions.

    Returns:
        TransactionDB: An instance of TransactionDB initialized with the transaction collection.
    """
    return transaction_db


async def get_session() -> AsyncGenerator[AsyncClientSession, None]:
    """
    Dependency to get an active session for database operations.

    Returns:
        AsyncSession: An instance of AsyncSession for database operations.
    """
    async with client.start_session() as session:
        yield session


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncClientSession, None]:
    """
    Dependency to get an active session for database operations.
    This function uses an async context manager to ensure that the session is properly closed after use.
    Returns:
        AsyncClientSession: An instance of AsyncClientSession for database operations.
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
