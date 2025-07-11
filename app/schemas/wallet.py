from typing import Annotated, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.db.models.wallet import WalletModel


class FundWalletSchema(BaseModel):
    """
    Schema for funding a wallet.

    Attributes:
        amount (float): The amount to fund the wallet with.
        currency (str): The currency of the amount being funded.
    """

    amount: Annotated[float, Field(gt=0, description="Amount to fund the wallet with")]
    currency: Annotated[str, Field(default="NGN", description="Currency of the amount")]
    customizations: Annotated[
        Optional[Dict[str, str]],
        Field(
            default=None,
            description="Customizations for the payment, including title and logo",
        ),
    ]

    model_config: ConfigDict = ConfigDict(
        json_schema_extra={
            "example": {
                "amount": 1000.0,
                "currency": "NGN",
                "customizations": {
                    "title": "Wallet Funding",
                    "logo": "https://example.com/logo.png",
                },
            }
        }
    )


class FundWalletResponseSchema(BaseModel):
    """
    Schema for the response after funding a wallet.

    Attributes:
        message (str): Confirmation message for the funding operation.
        link (str): Payment link for funding the wallet.
    """

    message: Annotated[str, Field(description="Confirmation message for the funding")]
    link: Annotated[str, Field(description="Payment link for funding the wallet")]


class WithdrawWalletSchema(BaseModel):
    """
    Schema for withdrawing from a wallet.

    Attributes:
        bank_code (str): The bank code for the withdrawal.
        account_number (str): The account number for the withdrawal.
        amount (float): The amount to withdraw from the wallet.
        currency (str): The currency of the amount being withdrawn.
    """

    bank_code: Annotated[str, Field(description="Bank code for withdrawal")]
    account_number: Annotated[str, Field(description="Account number for withdrawal")]
    amount: Annotated[
        float, Field(gt=0, description="Amount to withdraw from the wallet")
    ]
    currency: Annotated[str, Field(default="NGN", description="Currency of the amount")]

    model_config: ConfigDict = ConfigDict(
        json_schema_extra={
            "example": {
                "bank_code": "123456",
                "account_number": "1234567890",
                "amount": 5000.0,
                "currency": "NGN",
            }
        }
    )


class BankDetailsRequestSchema(BaseModel):
    """
    Schema for requesting bank details.

    Attributes:
        account_number (str): The account number for the bank account.
        bank_code (str): The bank code for the bank account.
    """

    account_number: Annotated[str, Field(description="Account number for the bank")]
    bank_code: Annotated[str, Field(description="Bank code for the bank")]


class BankDetailsSchema(BaseModel):
    account_number: Annotated[
        str, Field(description="Account number for the bank account")
    ]
    bank_code: Annotated[str, Field(description="Bank code for the bank account")]
    account_name: Annotated[
        str, Field(description="Name associated with the bank account")
    ]


class FlutterWaveCallbackSchema(BaseModel):
    """
    Schema for handling Flutterwave payment callbacks.

    Attributes:
        tx_ref (str): The transaction reference from Flutterwave.
        status (str): The status of the transaction.
        transaction_id (str): Unique identifier for the transaction.
    """

    tx_ref: Annotated[str, Field(description="Transaction reference from Flutterwave")]
    status: Annotated[str, Field(description="Status of the transaction")]
    transaction_id: Annotated[
        str, Field(description="Unique identifier for the transaction")
    ]

    model_config: ConfigDict = ConfigDict(
        json_schema_extra={
            "example": {
                "tx_ref": "txn_123456789",
                "status": "successful",
                "transaction_id": "1234567890",
            }
        }
    )


class BankSchema(BaseModel):
    """
    Schema for bank details.

    Attributes:
        id (str): Unique identifier for the bank.
        name (str): Name of the bank.
        code (str): Bank code.
    """

    id: Annotated[str, Field(description="Unique identifier for the bank")]
    name: Annotated[str, Field(description="Name of the bank")]
    code: Annotated[str, Field(description="Bank code")]

    model_config: ConfigDict = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "bank_123",
                "name": "Example Bank",
                "code": "123456",
            }
        }
    )


class BankResponseSchema(BaseModel):
    banks: Annotated[list[BankSchema], Field(description="List of banks")]

    model_config: ConfigDict = ConfigDict(
        json_schema_extra={
            "example": {
                "banks": [
                    {
                        "id": "bank_123",
                        "name": "Example Bank",
                        "code": "123456",
                    },
                    {
                        "id": "bank_456",
                        "name": "Another Bank",
                        "code": "654321",
                    },
                ]
            }
        }
    )
