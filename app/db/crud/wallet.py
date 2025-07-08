from enum import Enum
from typing import Literal, Optional

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from app.db.models.base import BaseDB
from app.db.models.wallet import WalletModel
from app.exceptions.types import DatabaseError, ObjectAlreadyExistsError, WalletError


class UpdateMode(Enum):
    ADD = "add"
    SUBTRACT = "subtract"


class WalletDB(BaseDB[WalletModel]):
    """
    WalletDB is a specialized database access layer for managing wallet-related operations.
    It extends the BaseDB class to provide CRUD operations specifically for WalletModel instances.
    """

    def __init__(self, collection: AsyncCollection):
        self.defaults = {
            "balance": 0.0,
            "currency": "NGN",
            "is_locked": False,
        }
        super().__init__(WalletModel, collection)

    async def get_by_user_id(
        self, user_id: str, session: Optional[AsyncClientSession] = None
    ) -> Optional[WalletModel]:
        """
        Retrieve a wallet by user ID.

        Args:
            user_id (str): The unique identifier of the user.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Optional[WalletModel]: An instance of WalletModel if a wallet for the user exists, otherwise None.
        """
        try:
            result = await self.collection.find_one(
                {"user_id": user_id}, session=session
            )
            return self.model(**result) if result else None
        except PyMongoError as e:
            raise DatabaseError(f"Error retrieving wallet by user ID: {e}")

    async def create(
        self,
        data: dict,
        defaults: Optional[dict] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> WalletModel:
        """
        Create a new wallet with the provided data.

        Args:
            data (dict): The data for the new wallet.
            defaults (Optional[dict]): Default values to apply if not provided in data.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            WalletModel: The created wallet instance.
        """
        if defaults is None:
            defaults = self.defaults
        user_id: str = data["user_id"]
        existing_wallet = await self.get_by_user_id(user_id, session=session)
        if existing_wallet:
            raise ObjectAlreadyExistsError(
                f"Wallet already exists for user ID: {user_id}"
            )
        data = {**defaults, **data}
        return await super().create(data, session=session)

    async def update_balance(
        self,
        user_id: str,
        amount: float,
        mode: UpdateMode,
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[WalletModel]:
        """
        Update the balance of a wallet by user ID.

        Args:
            user_id (str): The unique identifier of the user.
            amount (float): The amount to update the balance by.
            mode (UpdateMode): The mode of update, either ADD or SUBTRACT.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Optional[WalletModel]: The updated wallet instance if successful, otherwise None.

        Raises:
            WalletError: If the wallet is not found, is locked, or if the balance becomes negative.
        """
        wallet = await self.get_by_user_id(user_id, session=session)
        if not wallet:
            raise WalletError("Wallet not found for user ID")

        new_balance = (
            wallet.balance + amount
            if mode == UpdateMode.ADD
            else wallet.balance - amount
        )
        if new_balance < 0:
            raise WalletError("Insufficient balance for this operation")
        update_data = {"balance": new_balance}
        return await super().update(wallet.id, update_data, session=session)

    async def toggle_wallet_lock(
        self,
        user_id: str,
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[WalletModel]:
        """
        Lock or unlock the wallet for a user.

        Args:
            user_id (str): The unique identifier of the user.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Optional[WalletModel]: The updated wallet instance if successful, otherwise None.

        Raises:
            WalletError: If the wallet is not found.
        """
        wallet = await self.get_by_user_id(user_id, session=session)
        if not wallet:
            raise WalletError("Wallet not found for user ID")
        update_data = {"is_locked": not wallet.is_locked}
        return await super().update(wallet.id, update_data, session=session)

    async def toggle_wallet_activity(
        self,
        user_id: str,
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[WalletModel]:
        """
        Toggle the activity status of the wallet for a user.

        Args:
            user_id (str): The unique identifier of the user.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Optional[WalletModel]: The updated wallet instance if successful, otherwise None.

        Raises:
            WalletError: If the wallet is not found.
        """
        wallet = await self.get_by_user_id(user_id, session=session)
        if not wallet:
            raise WalletError("Wallet not found for user ID")
        update_data = {"is_active": not wallet.is_active}
        return await super().update(wallet.id, update_data, session=session)
