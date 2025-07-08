from typing import (
    Annotated,
    Callable,
    Tuple,
    TypeVar,
    Generic,
    Type,
    Optional,
    Sequence,
)
from bson import ObjectId
from pydantic import BeforeValidator
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from app.core.config import request_logger
from app.exceptions.types import DatabaseError

# Define a type alias for PyObjectId that uses BeforeValidator to ensure the value is a string
PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v))]


T = TypeVar("T")


class BaseDB(Generic[T]):
    """
    BaseDB is a generic asynchronous database access layer for MongoDB collections.
    This class provides common CRUD operations (Create, Read, Update, Delete) and utility methods for working with MongoDB collections in an asynchronous context. It is designed to be subclassed or instantiated with a specific Pydantic model and a Motor AsyncCollection.

    **Type Parameters:**
        T: The type of the model used to represent documents in the collection.
        model (Type[T]): The Pydantic model class used for data serialization/deserialization.
        collection (AsyncCollection): The Motor async collection instance to operate on.

    **Methods:**
        get_by_id(id: str) -> Optional[T]:
            Retrieve a single document by its unique identifier.
        get_all() -> Sequence[T]:
            Retrieve all documents from the collection.
        filter(filters: dict) -> Sequence[T]:
            Retrieve documents matching the specified filter criteria.
        create(data: dict, validate: Optional[Callable[[dict], dict]] = None) -> T:
            Insert a new document into the collection, optionally validating or transforming the data.
        update(id: str, updates: dict) -> Optional[T]:
            Update a document by its ID with the provided updates.
        delete(id: str) -> bool:
            Delete a document by its unique identifier.
        get_or_create(defaults: dict, filters: dict, validate: Optional[Callable[[dict], dict]] = None) -> T:
            Retrieve a document matching the filters, or create it with defaults if it does not exist.
    """

    def __init__(self, model: Type[T], collection: AsyncCollection):
        self.model = model
        self.collection = collection

    async def get_by_id(
        self, id: str, session: Optional[AsyncClientSession] = None
    ) -> Optional[T]:
        """
        Retrieve a single document from the collection by its unique identifier.

        Args:
            id (str): The unique identifier of the document to retrieve.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Optional[T]: An instance of the model if a document with the given ID exists, otherwise None.

        Raises:
            DatabaseError: If there is an error retrieving the document from the collection.
        """
        try:
            try:
                obj_id = ObjectId(id)
            except Exception:
                raise DatabaseError(f"Invalid ObjectId format for id: {id}")
            result = await self.collection.find_one({"_id": obj_id}, session=session)
            return self.model(**result) if result else None
        except PyMongoError as e:
            raise DatabaseError(
                f"Error retrieving document with id {id} from collection {self.collection.name}: {str(e)}"
            )

    async def get_all(
        self, session: Optional[AsyncClientSession] = None
    ) -> Sequence[T]:
        """
        Asynchronously retrieves all documents from the collection and returns them as a sequence of model instances.

        Args:
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Sequence[T]: A sequence of model instances constructed from all documents in the collection.

        Raises:
            DatabaseError: If there is an error retrieving documents from the collection.
        """
        try:
            result = await self.collection.find({}, session=session).to_list(
                length=None
            )
            return [self.model(**doc) for doc in result]
        except PyMongoError as e:
            raise DatabaseError(
                f"Error retrieving documents from collection {self.collection.name}: {str(e)}"
            )

    async def filter(
        self, filters: dict, session: Optional[AsyncClientSession] = None
    ) -> Sequence[T]:
        """
        Asynchronously retrieves documents from the collection that match the given filters.

        Args:
            filters (dict): A dictionary specifying the filter criteria for querying the collection.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Sequence[T]: A sequence of model instances corresponding to the documents that match the filters.

        Raises:
            DatabaseError: If there is an error filtering documents in the collection.
        """
        try:
            if not isinstance(filters, dict):
                raise DatabaseError("Filters must be a dictionary")
            result = await self.collection.find(filters, session=session).to_list(
                length=None
            )
            return [self.model(**doc) for doc in result]
        except PyMongoError as e:
            raise DatabaseError(
                f"Error filtering documents in collection {self.collection.name} with filters {filters}"
                f": {str(e)}"
            )

    async def create(
        self,
        data: dict,
        validate: Optional[Callable[[dict], dict]] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> T:
        """
        Asynchronously creates a new document in the collection.

        Args:
            data (dict): The data to be inserted into the collection.
            validate (Optional[Callable[[dict], dict]]): An optional callable to validate or transform the data before insertion.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            T: An instance of the model initialized with the inserted data, including the generated '_id' field.

        Raises:
            DatabaseError: If there is an error creating the document in the collection or if the data is not a dictionary.
        """
        try:
            if not isinstance(data, dict):
                raise DatabaseError("Data must be a dictionary")
            if validate:
                data = validate(data)
            result = await self.collection.insert_one(data, session=session)
            data["_id"] = result.inserted_id
            return self.model(**data)
        except PyMongoError as e:
            raise DatabaseError(
                f"Error creating document in collection {self.collection.name}: {str(e)}"
            )

    async def update(
        self, id: str, updates: dict, session: Optional[AsyncClientSession] = None
    ) -> Optional[T]:
        """
        Asynchronously updates a document in the collection by its ID with the provided updates.

        Args:
            id (str): The string representation of the document's ObjectId.
            updates (dict): A dictionary containing the fields to update and their new values.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Optional[T]: The updated document if the update was successful, or None if the ID is invalid or the document does not exist.

        Raises:
            DatabaseError: If there is an error updating the document in the collection or if the updates are not a dictionary.
        """
        try:
            if not isinstance(updates, dict):
                raise DatabaseError("Updates must be a dictionary")
            try:
                obj_id = ObjectId(id)
            except Exception:
                raise DatabaseError(f"Invalid ObjectId format for id: {id}")
            await self.collection.update_one(
                {"_id": obj_id}, {"$set": updates}, session=session
            )
            return await self.get_by_id(id, session=session)
        except PyMongoError as e:
            raise DatabaseError(
                f"Error updating document with id {id} in collection {self.collection.name}: {str(e)}"
            )

    async def delete(
        self, id: str, session: Optional[AsyncClientSession] = None
    ) -> bool:
        """
        Asynchronously deletes a document from the collection by its unique identifier.

        Args:
            id (str): The string representation of the document's ObjectId.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            bool: True if a document was deleted, False otherwise (including if the id is invalid).

        Raises:
            DatabaseError: If there is an error deleting the document from the collection or if the id is not a valid ObjectId.
        """
        try:
            try:
                obj_id = ObjectId(id)
            except Exception:
                raise DatabaseError(f"Invalid ObjectId format for id: {id}")
            result = await self.collection.delete_one({"_id": obj_id}, session=session)
            return result.deleted_count > 0
        except PyMongoError as e:
            raise DatabaseError(
                f"Error deleting document with id {id} from collection {self.collection.name}: {str(e)}"
            )

    async def get_or_create(
        self,
        defaults: dict,
        filters: dict,
        validate: Optional[Callable[[dict], dict]] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> Tuple[T, bool]:
        """
        Retrieves a document from the collection matching the given filters.
        If such a document exists, returns an instance of the model initialized with the document data.
        If not, creates a new document with the combined filters and defaults, optionally validating the data.

        Args:
            defaults (dict): Default values to use when creating a new document.
            filters (dict): Query parameters to find an existing document.
            validate (Optional[Callable[[dict], dict]]): Optional function to validate or modify the data before creation.
            session (Optional[AsyncClientSession]): An optional session for the database operation.

        Returns:
            Tuple[T, bool]: A tuple containing the model instance and a boolean indicating whether a new document was created.

        Raises:
            DatabaseError: If there is an error retrieving or creating the document in the collection, or if the filters or defaults are not dictionaries.
        """
        try:
            if not isinstance(defaults, dict) or not isinstance(filters, dict):
                raise DatabaseError("Defaults and filters must be dictionaries")
            doc = await self.collection.find_one(filters)
            if doc:
                return self.model(**doc), False
            return (
                await self.create(
                    self.collection,
                    {**filters, **defaults},
                    validate=validate,
                    session=session,
                ),
                True,
            )
        except PyMongoError as e:
            raise DatabaseError(
                f"Error retrieving or creating document in collection {self.collection.name} with filters {filters} and defaults {defaults}: {str(e)}"
            )
