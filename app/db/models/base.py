from typing import Annotated, Callable, TypeVar, Generic, Type, Optional, Sequence
from bson import ObjectId
from pydantic import BeforeValidator
from pymongo.asynchronous.collection import AsyncCollection

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

    async def get_by_id(self, id: str) -> Optional[T]:
        """
        Retrieve a single document from the collection by its unique identifier.

        Args:
            id (str): The unique identifier of the document to retrieve.

        Returns:
            Optional[T]: An instance of the model if a document with the given ID exists, otherwise None.
        """
        try:
            obj_id = ObjectId(id)
        except Exception:
            return None
        result = await self.collection.find_one({"_id": obj_id})
        return self.model(**result) if result else None

    async def get_all(self) -> Sequence[T]:
        """
        Asynchronously retrieves all documents from the collection and returns them as a sequence of model instances.

        Returns:
            Sequence[T]: A sequence of model instances constructed from all documents in the collection.
        """
        result = await self.collection.find({}).to_list(length=None)
        return [self.model(**doc) for doc in result]

    async def filter(self, filters: dict) -> Sequence[T]:
        """
        Asynchronously retrieves documents from the collection that match the given filters.

        Args:
            filters (dict): A dictionary specifying the filter criteria for querying the collection.

        Returns:
            Sequence[T]: A sequence of model instances corresponding to the documents that match the filters.
        """
        result = await self.collection.find(filters).to_list(length=None)
        return [self.model(**doc) for doc in result]

    async def create(
        self,
        data: dict,
        validate: Optional[Callable[[dict], dict]] = None,
    ) -> T:
        """
        Asynchronously creates a new document in the collection.

        Args:
            data (dict): The data to be inserted into the collection.
            validate (Optional[Callable[[dict], dict]]): An optional callable to validate or transform the data before insertion.

        Returns:
            T: An instance of the model initialized with the inserted data, including the generated '_id' field.
        """
        if validate:
            data = validate(data)
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return self.model(**data)

    async def update(self, id: str, updates: dict) -> Optional[T]:
        """
        Asynchronously updates a document in the collection by its ID with the provided updates.

        Args:
            id (str): The string representation of the document's ObjectId.
            updates (dict): A dictionary containing the fields to update and their new values.

        Returns:
            Optional[T]: The updated document if the update was successful, or None if the ID is invalid or the document does not exist.
        """
        try:
            obj_id = ObjectId(id)
        except Exception:
            return None
        await self.collection.update_one({"_id": obj_id}, {"$set": updates})
        return await self.get_by_id(self.collection, id)

    async def delete(self, id: str) -> bool:
        """
        Asynchronously deletes a document from the collection by its unique identifier.

        Args:
            id (str): The string representation of the document's ObjectId.

        Returns:
            bool: True if a document was deleted, False otherwise (including if the id is invalid).
        """
        try:
            obj_id = ObjectId(id)
        except Exception:
            return False
        result = await self.collection.delete_one({"_id": obj_id})
        return result.deleted_count > 0

    async def get_or_create(
        self,
        defaults: dict,
        filters: dict,
        validate: Optional[Callable[[dict], dict]] = None,
    ) -> T:
        """
        Retrieves a document from the collection matching the given filters.
        If such a document exists, returns an instance of the model initialized with the document data.
        If not, creates a new document with the combined filters and defaults, optionally validating the data.

        Args:
            defaults (dict): Default values to use when creating a new document.
            filters (dict): Query parameters to find an existing document.
            validate (Optional[Callable[[dict], dict]]): Optional function to validate or modify the data before creation.

        Returns:
            T: An instance of the model, either retrieved or newly created.
        """
        doc = await self.collection.find_one(filters)
        if doc:
            return self.model(**doc)
        return await self.create(
            self.collection, {**filters, **defaults}, validate=validate
        )
