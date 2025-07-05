from functools import lru_cache

from fastapi.security import OAuth2PasswordBearer
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logger import setup_logger


class Settings(BaseSettings):
    MONGO_URI: str
    MONGO_DB_NAME: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


request_logger = setup_logger("request_logger", "app/logs/request.log")
