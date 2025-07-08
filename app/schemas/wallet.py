from typing import Annotated, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.db.models.wallet import WalletModel


class Customizations(BaseModel):
    """
    Customizations for the payment.

    Attributes:
        title (str): Title of the payment.
        description (str): Description of the payment.
    """

    title: Annotated[
        str, Field(default="Wallet Funding", description="Title of the payment")
    ]
    logo: Annotated[
        Optional[str], Field(default=None, description="Logo URL for the payment")
    ]


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
        Optional[Customizations],
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
        amount (float): The amount to withdraw from the wallet.
        currency (str): The currency of the amount being withdrawn.
    """

    amount: Annotated[
        float, Field(gt=0, description="Amount to withdraw from the wallet")
    ]
    currency: Annotated[str, Field(default="NGN", description="Currency of the amount")]


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
