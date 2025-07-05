from typing import Callable, Dict, Optional

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from app.core.security import hash_password, verify_password
from app.db.models.base import BaseDB
from app.db.models.user import UserModel
from app.exceptions.types import DatabaseError


class UserDB(BaseDB[UserModel]):
    """
    UserDB provides asynchronous CRUD operations and utility methods for user data management in the database.
    This class extends BaseDB for the UserModel, adding user-specific logic such as password hashing and
    lookup by email. It includes methods for validating user data, creating users, retrieving users by email,
    and a get_or_create utility for upserting users.

    Methods:
        __init__(collection: AsyncCollection)
            Initializes the UserDB with the specified async collection.
        validate_user_data(data: dict) -> dict
            Validates and processes user data, hashing the password if present.
        create(data: dict) -> UserModel
            Asynchronously creates a new user record, ensuring password is hashed.
        get_by_email(email: str) -> Optional[UserModel]
            Retrieves a user by their email address.
        get_or_create(filters: dict, defaults: Optional[dict] = None, validate: Optional[Callable[[dict], dict]] = None) -> UserModel
            Retrieves an existing user matching filters or creates a new one with defaults and validation.
    """

    def __init__(self, collection: AsyncCollection):
        super().__init__(UserModel, collection)

    @staticmethod
    def validate_user_data(data: dict) -> dict:
        """
        Validates and processes user data by extracting the 'password' field, if present,
        hashing it, and storing the result under the 'hashed_password' key.

        Args:
            data (dict): A dictionary containing user data, potentially including a 'password' key.

        Returns:
            dict: The updated user data dictionary with the password hashed (if provided) and stored as 'hashed_password'.
        """
        password = data.pop("password", None)
        if password:
            data["hashed_password"] = hash_password(password)
        return data

    async def authenticate(
        self, email: str, password: str, session: Optional[AsyncClientSession] = None
    ) -> Optional[UserModel]:
        """
        Authenticates a user by email and password.

        Args:
            email (str): The user's email address.
            password (str): The user's plain-text password.
            session (Optional[AsyncClientSession], optional): An optional session for the database operation.

        Returns:
            Optional[UserModel]: An instance of UserModel if authentication is successful, otherwise None.
        """
        user: Optional[UserModel] = await self.get_by_email(email, session=session)
        if user and verify_password(password, user.hashed_password):
            return user
        return None

    async def create(
        self,
        data: dict,
        defaults: Optional[Dict] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> UserModel:
        """
        Asynchronously creates a new user record in the database.

        Args:
            data (dict): A dictionary containing the user data to be created.
            defaults (Optional[Dict], optional): Default values to use when creating a new user.
                Defaults to {"is_active": True, "is_admin": False}.
            session (Optional[AsyncClientSession], optional): An optional session for the database operation.

        Returns:
            UserModel: The newly created user model instance.

        Raises:
            ValidationError: If the provided user data fails validation.
        """
        if defaults is None:
            defaults = {"is_active": True, "is_admin": False}
        data = {**defaults, **data}
        return await super().create(data, self.validate_user_data, session=session)

    async def get_by_email(
        self, email: str, session: Optional[AsyncClientSession] = None
    ) -> Optional[UserModel]:
        """
        Asynchronously retrieves a user document from the database by email.

        Args:
            email (str): The email address of the user to retrieve.
            session (Optional[AsyncClientSession], optional): An optional session for the database operation.

        Returns:
            Optional[UserModel]: An instance of UserModel if a user with the given email exists, otherwise None.
        """
        try:
            doc = await self.collection.find_one({"email": email}, session=session)
            return self.model(**doc) if doc else None
        except PyMongoError as e:
            raise DatabaseError(f"Error retrieving user by email: {e}")

    async def get_or_create(
        self,
        filters: dict,
        defaults: Optional[dict] = None,
        validate: Optional[Callable[[dict], dict]] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> UserModel:
        """
        Retrieve an existing user matching the given filters or create a new one with the provided defaults.

        Args:
            filters (dict): Dictionary of field lookups to filter existing users.
            defaults (Optional[dict], optional): Default values to use when creating a new user if one does not exist.
                Defaults to {"is_active": True, "is_admin": False}.
            validate (Optional[Callable[[dict], dict]], optional): Optional function to validate or modify user data before creation.
                Defaults to self.validate_user_data.
            session (Optional[AsyncClientSession], optional): An optional session for the database operation.

        Returns:
            UserModel: The retrieved or newly created user instance.
        """
        if defaults is None:
            defaults = {"is_active": True, "is_admin": False}
        if validate is None:
            validate = self.validate_user_data
        return await super().get_or_create(filters, defaults, validate, session=session)
