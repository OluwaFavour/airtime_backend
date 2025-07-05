from app.db.session import database
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
