from pymongo import AsyncMongoClient
from app.core.config import get_settings

settings = get_settings()
client = AsyncMongoClient(settings.MONGO_URI)
database = client.get_database(settings.MONGO_DB_NAME)
