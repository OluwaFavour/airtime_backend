from typing import Annotated
from fastapi import APIRouter, Depends, Form

from pymongo.read_concern import ReadConcern
from pymongo import WriteConcern
from pymongo.asynchronous.client_session import AsyncClientSession

from app.api.dependencies import (
    get_current_active_user,
    get_session,
    get_user_db,
    get_wallet_db,
)
from app.db.crud.wallet import WalletDB
from app.exceptions.types import CredentialError, ObjectAlreadyExistsError
from app.core.security import create_access_token
from app.db.crud.user import UserDB
from app.db.models.user import UserModel
from app.schemas.auth import (
    TokenSchema,
    UserLoginSchema,
    UserRegistrationSchema,
    UserResponseSchema,
)


router = APIRouter()


@router.post("/login")
async def login(
    user: Annotated[UserLoginSchema, Form()],
    user_db: Annotated[UserDB, Depends(get_user_db)],
) -> TokenSchema:
    """
    Authenticate a user and return a JWT token.

    Args:
        user (UserLoginSchema): The form containing user credentials.
        user_db (UserDB): The UserDB instance for database operations.

    Returns:
        TokenSchema: The JWT token for the authenticated user.

    Raises:
        CredentialError: If the username or password is invalid.
    """
    authenticated_user = await user_db.authenticate(user.email, user.password)
    if not authenticated_user:
        raise CredentialError("Invalid username or password")

    access_token = create_access_token({"sub": str(authenticated_user.id)})
    return TokenSchema(access_token=access_token, token_type="bearer")


@router.post("/register")
async def register(
    form_data: Annotated[UserRegistrationSchema, Form()],
    user_db: Annotated[UserDB, Depends(get_user_db)],
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
    session: Annotated[AsyncClientSession, Depends(get_session)],
) -> UserResponseSchema:
    """
    Register a new user.

    Args:
        form_data (UserRegistrationSchema): The form data containing user registration details.
        user_db (UserDB): The UserDB instance for database operations.

    Returns:
        UserResponseSchema: The newly created user model instance.

    Raises:
        ObjectAlreadyExistsError: If a user with the provided email already exists.
    """
    async with await session.start_transaction(
        write_concern=WriteConcern("majority"), read_concern=ReadConcern("local")
    ):
        try:
            existing_user = await user_db.get_by_email(form_data.email, session=session)
            if existing_user:
                raise ObjectAlreadyExistsError("User with this email already exists")
            new_user = await user_db.create(
                {
                    "email": form_data.email,
                    "password": form_data.password,
                },
                session=session,
            )
            # Create a wallet for the new user
            wallet_data = {
                "user_id": str(new_user.id),
            }
            wallet = await wallet_db.create(wallet_data, session=session)
            return UserResponseSchema(
                **new_user.model_dump(),
                wallet=wallet,
            )
        except ObjectAlreadyExistsError:
            raise


@router.get("/me", response_model=UserModel)
async def get_current_user(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
) -> UserModel:
    """
    Get the currently authenticated user.

    Args:
        current_user (UserModel): The currently authenticated user.

    Returns:
        UserModel: The current user's model instance.
    """
    return current_user
