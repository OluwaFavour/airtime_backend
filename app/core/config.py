from functools import lru_cache
from typing import List

from fastapi.security import OAuth2PasswordBearer
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logger import setup_logger


class Settings(BaseSettings):
    MONGO_URI: str
    MONGO_DB_NAME: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FLUTTERWAVE_LINK_EXPIRY_MINUTES: int = 30
    FLUTTERWAVE_REDIRECT_URL: str = "/wallet/flutterwave/callback"
    FLUTTERWAVE_SECRET_KEY: str
    FLUTTERWAVE_SESSION_DURATION_MINUTES: int = 30
    FLUTTERWAVE_PAYMENT_OPTIONS: List[str] = [
        "card",
        "ussd",
        "banktransfer",
        "account",
        "internetbanking",
        "applepay",
        "googlepay",
        "enaira",
        "opay",
    ]
    FLUTTERWAVE_WEBHOOK_HASH: str
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672//"
    REDIS_URL: str = "redis://redis:6379"
    REDIS_CHANNEL: str
    APP_ADDRESS: str = "http://127.0.0.1:8000/api/v1"
    APP_NAME: str = "Airtime Backend API"

    model_config = SettingsConfigDict(
        env_file=".env",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


request_logger = setup_logger("request_logger", "app/logs/request.log")
app_logger = setup_logger("app_logger", "app/logs/app.log")
websocket_logger = setup_logger("websocket_logger", "app/logs/websocket.log")
rabbitmq_logger = setup_logger("rabbitmq_logger", "app/logs/rabbitmq.log")
