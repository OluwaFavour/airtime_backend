from typing import Annotated
from fastapi import APIRouter, Depends, Form, Query, Request, Response, status

from fastapi.responses import HTMLResponse
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.read_concern import ReadConcern
from pymongo import WriteConcern
from app.api.dependencies import (
    get_current_active_user,
    get_session,
    get_wallet_db,
    get_transaction_db,
)
from app.core.config import get_settings, request_logger
from app.db.crud.transactions import TransactionDB
from app.db.crud.wallet import UpdateMode, WalletDB
from app.db.models.user import UserModel
from app.db.models.wallet import (
    WalletModel,
    TransactionStatus,
    TransactionType,
    TransactionModel,
)
from app.exceptions.types import ObjectNotFoundError, PaymentFailedError, WalletError
from app.schemas.wallet import (
    FlutterWaveCallbackSchema,
    FundWalletResponseSchema,
    FundWalletSchema,
    WithdrawWalletSchema,
)
from app.rabbitmq.publisher import publish_payment_event
from app.services.payment_gateway import FlutterWaveClient, get_flutterwave_client


router = APIRouter()
settings = get_settings()


@router.get("/")
async def get_wallet(
    user: Annotated[UserModel, Depends(get_current_active_user)],
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
) -> WalletModel:
    """
    Retrieve the wallet information for the current user.

    Args:
        user (UserModel): The currently authenticated user.
        wallet_db (WalletDB): The WalletDB instance for database operations.

    Returns:
        WalletModel: The wallet information of the user.

    Raises:
        ObjectNotFoundError: If the wallet for the user does not exist.
    """
    wallet = await wallet_db.get_by_user_id(user.id)
    if not wallet:
        raise ObjectNotFoundError("Wallet not found for the user.")
    return wallet


@router.post("/toggle-activity")
async def toggle_activitiy(
    user: Annotated[UserModel, Depends(get_current_active_user)],
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
    session: Annotated[AsyncClientSession, Depends(get_session)],
) -> WalletModel:
    """
    Toggle the activity status of the wallet for the current user.

    Args:
        user (UserModel): The currently authenticated user.
        wallet_db (WalletDB): The WalletDB instance for database operations.
        session (AsyncClientSession): The database session.

    Returns:
        WalletModel: The updated wallet information after toggling activity status.

    Raises:
        ObjectNotFoundError: If the wallet for the user does not exist.
    """
    async with await session.start_transaction(
        write_concern=WriteConcern("majority"), read_concern=ReadConcern("snapshot")
    ):
        return await wallet_db.toggle_wallet_activity(user.id, session=session)


@router.post("/fund")
async def fund_wallet(
    user: Annotated[UserModel, Depends(get_current_active_user)],
    data: Annotated[FundWalletSchema, Form()],
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
    transaction_db: Annotated[TransactionDB, Depends(get_transaction_db)],
    session: Annotated[AsyncClientSession, Depends(get_session)],
    flutterwave_client: Annotated[FlutterWaveClient, Depends(get_flutterwave_client)],
) -> FundWalletResponseSchema:
    """
    Fund the wallet for the current user.

    Args:
        user (UserModel): The currently authenticated user.
        data (FundWalletSchema): The form data containing the amount to fund.
        wallet_db (WalletDB): The WalletDB instance for database operations.
        transaction_db (TransactionDB): The TransactionDB instance for transaction records.
        session (AsyncClientSession): The database session.
        flutterwave_client (FlutterWaveClient): The payment gateway client for processing payments.

    Returns:
        FundWalletResponseSchema: The response containing the updated wallet information and transaction reference.

    Raises:
        ObjectNotFoundError: If the wallet for the user does not exist.
    """
    wallet = await wallet_db.get_by_user_id(user.id)
    if not wallet:
        raise ObjectNotFoundError("Wallet not found for the user.")
    if wallet.is_locked:
        raise WalletError("Wallet is locked. Cannot perform any wallet operations.")
    if not wallet.is_locked:
        await wallet_db.toggle_wallet_lock(
            user.id
        )  # Lock the wallet to prevent concurrent funding operations
    try:
        async with await session.start_transaction(
            write_concern=WriteConcern("majority"), read_concern=ReadConcern("snapshot")
        ):
            # Fund via payment gateway before updating the wallet balance
            flutterwave_response = await flutterwave_client.initiate_payment(
                user_id=str(user.id),
                amount=data.amount,
                email=user.email,
                currency=data.currency,
                customizations=(
                    data.customizations.model_dump() if data.customizations else None
                ),
            )
            # Create a transaction record for the funding
            transaction_record = TransactionModel(
                user_id=user.id,
                wallet_id=wallet.id,
                amount=data.amount,
                currency=data.currency,
                type=TransactionType.FUND.value,
                status=TransactionStatus.PENDING.value,
                reference=flutterwave_response["tx_ref"],
                timestamp=flutterwave_response["created_at"],
            )
            await transaction_db.create(
                transaction_record.model_dump(), session=session
            )
            response = FundWalletResponseSchema(
                message="Wallet funded successfully!",
                link=flutterwave_response.get("data", {}).get("link", ""),
            )
            if not response.link:
                raise PaymentFailedError("Payment link not provided by Flutterwave.")
            return response
    except Exception as e:
        if wallet and wallet.is_locked:
            await wallet_db.toggle_wallet_lock(user.id)
        raise e  # Re-raise the exception to be handled by the global error handler


@router.get("/flutterwave/callback", response_class=HTMLResponse)
async def payment_redirect(request: Request):
    # You may want to extract tx_ref for display/tracking
    tx_ref = request.query_params.get("tx_ref")

    html = f"""
    <html>
    <head><title>Payment Complete</title></head>
    <body>
        <h2>✅ Payment initiated successfully!</h2>
        <p>Your transaction is being verified. You’ll receive a confirmation soon.</p>
        <p>Transaction Reference: <strong>{tx_ref}</strong></p>

        <script>
            const txRef = "{tx_ref}";
            const socket = new WebSocket("ws://{settings.APP_ADDRESS.replace("http://", "").replace("https://", "")}/ws/wallet");

            socket.onopen = () => {{
                socket.send(JSON.stringify({{ tx_ref: txRef }}));
            }};

            socket.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                if (data.status === "success") {{
                    alert("Wallet credited! You can now continue.");
                }}
            }};
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/flutterwave/webhook")
async def flutterwave_webhook(request: Request):
    """
    Handle the webhook from FlutterWave for payment notifications.

    Args:
        request (Request): The incoming request containing the webhook data.

    Returns:
        dict: A response indicating successful processing of the webhook.
    """
    # Validate the webhook signature
    signature = request.headers.get("verif-hash")
    if not signature or not get_flutterwave_client().verify_webhook_signature(
        signature
    ):
        request_logger.error(
            "Invalid webhook signature received.",
            extra={"signature": signature},
        )
        return Response(
            status_code=status.HTTP_200_OK,
        )

    data = await request.json()
    data["signature"] = signature

    # Start Background task to process the webhook data
    await publish_payment_event(data)
    return Response(
        status_code=status.HTTP_200_OK,
    )


@router.post("/withdraw")
async def withdraw_from_wallet(
    user: Annotated[UserModel, Depends(get_current_active_user)],
    data: Annotated[WithdrawWalletSchema, Form()],
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
    session: Annotated[AsyncClientSession, Depends(get_session)],
) -> WalletModel:
    """
    Withdraw from the wallet for the current user.

    Args:
        user (UserModel): The currently authenticated user.
        data (WithdrawWalletSchema): The form data containing the amount to withdraw.
        wallet_db (WalletDB): The WalletDB instance for database operations.
        session (AsyncClientSession): The database session.

    Returns:
        WalletModel: The updated wallet information after withdrawal.

    Raises:
        ObjectNotFoundError: If the wallet for the user does not exist.
    """
    wallet = await wallet_db.get_by_user_id(user.id)
    if not wallet:
        raise ObjectNotFoundError("Wallet not found for the user.")
    if wallet.is_locked:
        raise WalletError("Wallet is locked. Cannot perform any wallet operations.")
    if wallet.balance < data.amount:
        raise WalletError("Insufficient balance for withdrawal.")
    if not wallet.is_locked:
        await wallet_db.toggle_wallet_lock(
            user.id
        )  # Lock the wallet to prevent concurrent withdrawal operations
    async with await session.start_transaction(
        write_concern=WriteConcern("majority"), read_concern=ReadConcern("snapshot")
    ):
        # TODO: Implement withdrawal logic, via payment gateway before updating the wallet balance
        # TODO: Create a transaction record for the withdrawal
        return await wallet_db.update_balance(
            user.id, data.amount, mode="subtract", session=session
        )
