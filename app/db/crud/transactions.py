from typing import Optional

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from app.db.models.base import BaseDB
from app.db.models.wallet import TransactionModel
from app.exceptions.types import (
    DatabaseError,
    ObjectAlreadyExistsError,
    TransactionError,
)


class TransactionDB(BaseDB[TransactionModel]):
    """
    TransactionDB is a specialized database access layer for managing transaction-related operations.
    It extends the BaseDB class to provide CRUD operations specifically for TransactionModel instances.
    """

    def __init__(self, collection: AsyncCollection):
        super().__init__(TransactionModel, collection)

    async def get_by_reference(
        self, reference: str, session: Optional[AsyncClientSession] = None
    ) -> Optional[TransactionModel]:
        """
        Retrieve a transaction by its reference.

        Args:
            reference (str): The unique reference of the transaction.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Optional[TransactionModel]: An instance of TransactionModel if a transaction with the reference exists, otherwise None.
        """
        try:
            result = await self.collection.find_one(
                {"reference": reference}, session=session
            )
            return self.model(**result) if result else None
        except PyMongoError as e:
            raise DatabaseError(f"Error retrieving transaction by reference: {e}")
