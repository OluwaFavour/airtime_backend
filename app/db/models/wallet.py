from datetime import datetime
from enum import Enum
from typing import Annotated, Optional
from bson import CodecOptions
from pydantic import BaseModel, ConfigDict, Field

from app.db.config import database
from app.db.models.base import PyObjectId


class WalletModel(BaseModel):
    id: Annotated[Optional[PyObjectId], Field(alias="_id")] = None
    user_id: Annotated[str, Field(description="ID of the user who owns the wallet")]
    balance: Annotated[
        float, Field(default=0.0, description="Current balance in the wallet")
    ]
    currency: Annotated[
        str, Field(default="NGN", description="Currency of the wallet balance")
    ]
    is_locked: Annotated[
        bool, Field(default=False, description="Is the wallet locked for transactions?")
    ]
    is_active: Annotated[bool, Field(default=True, description="Is the wallet active?")]

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            PyObjectId: str,
        },
        json_schema_extra={
            "example": {
                "user_id": "60c72b2f9b1e8d3f4c8b4567",
                "balance": 100.0,
                "currency": "NGN",
                "is_locked": False,
                "is_active": True,
            }
        },
    )


class WalletCollection(BaseModel):
    wallets: list[WalletModel]


# Create the wallet collection in the database
wallet_collection = database.get_collection("wallets")


class TransactionType(Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    FUND = "fund"
    WITHDRAW = "withdraw"


class TransactionStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class TransactionModel(BaseModel):
    id: Annotated[Optional[PyObjectId], Field(alias="_id")] = None
    user_id: Annotated[
        str, Field(description="ID of the user associated with the transaction")
    ]
    wallet_id: Annotated[
        str,
        Field(description="ID of the wallet associated with the transaction"),
    ]
    amount: Annotated[float, Field(description="Amount involved in the transaction")]
    currency: Annotated[
        str, Field(default="NGN", description="Currency of the transaction amount")
    ]
    type: Annotated[
        str,
        Field(description="Type of transaction (e.g., 'credit', 'debit')"),
    ]
    status: Annotated[
        str,
        Field(
            default=TransactionStatus.PENDING.value,
            description="Status of the transaction",
        ),
    ]
    reference: Annotated[
        Optional[str],
        Field(default=None, description="Optional reference for the transaction"),
    ]
    timestamp: Annotated[
        str, Field(description="Timestamp of the transaction in ISO format")
    ]

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            PyObjectId: str,
        },
        json_schema_extra={
            "example": {
                "user_id": "60c72b2f9b1e8d3f4c8b4567",
                "wallet_id": "60c72b2f9b1e8d3f4c8b4567",
                "amount": 50.0,
                "currency": "NGN",
                "type": "credit",
                "status": "pending",
                "reference": "txn_123456",
                "timestamp": "2023-10-01T12:00:00Z",
            }
        },
    )


class TransactionCollection(BaseModel):
    transactions: list[TransactionModel]


# Create the transaction collection in the database
transaction_collection = database.get_collection("transactions")
