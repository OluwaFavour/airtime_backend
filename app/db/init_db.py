from pymongo.asynchronous.database import AsyncDatabase


async def init_indexes(database: AsyncDatabase):
    """
    Initialize indexes for the database collections.

    Args:
        database (AsyncDatabase): The database instance to initialize indexes for.
    """
    # Create unique index on user_id in the users collection
    await database.get_collection("users").create_index("email", unique=True)

    # Create unique index on user_id in the wallets collection
    await database.get_collection("wallets").create_index("user_id", unique=True)
