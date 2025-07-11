from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Form, Path, Request, Response, status

from fastapi.responses import HTMLResponse, RedirectResponse
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.read_concern import ReadConcern
from pymongo import WriteConcern
from app.api.dependencies import (
    get_current_active_user,
    get_session,
    get_wallet_db,
    get_transaction_db,
)
from app.core.config import get_settings, request_logger, templates
from app.db.crud.transactions import TransactionDB
from app.db.crud.wallet import WalletDB
from app.db.models.user import UserModel
from app.db.models.wallet import (
    WalletModel,
    TransactionStatus,
    TransactionType,
    TransactionModel,
)
from app.exceptions.types import (
    BankVerificationError,
    ObjectNotFoundError,
    PaymentFailedError,
    TransactionError,
    WalletError,
)
from app.schemas.wallet import (
    BankDetailsRequestSchema,
    BankDetailsSchema,
    BankResponseSchema,
    BankSchema,
    FundWalletResponseSchema,
    FundWalletSchema,
    WithdrawWalletSchema,
)
from app.rabbitmq.publisher import publish_flutter_event
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
    await wallet_db.toggle_wallet_lock(
        user.id, lock=True  # Lock the wallet to prevent concurrent funding operations
    )
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
                customizations=(data.customizations if data.customizations else None),
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
    except PaymentFailedError as e:
        if e.unlock_wallet:
            await wallet_db.toggle_wallet_lock(user.id, lock=False)
        raise e


@router.get("/flutterwave/callback", response_class=HTMLResponse)
async def payment_redirect(
    request: Request,
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
    transaction_db: Annotated[TransactionDB, Depends(get_transaction_db)],
    session: Annotated[AsyncClientSession, Depends(get_session)],
):
    tx_ref = request.query_params.get("tx_ref")
    flutterwave_status = request.query_params.get("status")
    if not tx_ref or not flutterwave_status or flutterwave_status != "successful":
        if tx_ref:
            async with await session.start_transaction(
                write_concern=WriteConcern("majority"),
                read_concern=ReadConcern("snapshot"),
            ):
                # If the transaction reference is invalid or status is not successful
                request_logger.error(
                    f"Invalid transaction reference or status: {tx_ref}, {flutterwave_status}"
                )
                # Unsuccessful or invalid transaction
                transaction = await transaction_db.get_by_reference(tx_ref)
                if transaction:
                    # Update the transaction status to failed
                    await transaction_db.update(
                        transaction.id,
                        {"status": TransactionStatus.FAILED.value},
                    )
                    # Unlock the wallet if it was locked during funding
                    await wallet_db.toggle_wallet_lock(transaction.user_id, lock=False)
        return templates.TemplateResponse(
            name="wallet/payment_failed.html",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return templates.TemplateResponse(
        name="wallet/payment_success.html",
        context={
            "tx_ref": tx_ref,
            "route": "/ws/wallet",
            "domain": settings.APP_ADDRESS.replace("http://", "").replace(
                "https://", ""
            ),
        },
    )


@router.get(
    "/withdraw/success/{tx_ref}", response_class=HTMLResponse, name="withdraw_success"
)
async def withdraw_success(tx_ref: Annotated[str, Path()], request: Request):
    """
    Render a success page after a successful withdrawal.

    Args:
        request (Request): The incoming request object.

    Returns:
        HTMLResponse: An HTML response indicating the withdrawal was successful.
    """
    html = f"""
    <html>
    <head><title>Withdrawal Successful</title></head>
    <body>
        <h2>✅ Withdrawal Successful!</h2>
        <p>Your withdrawal has been processed successfully.</p>
        <p>You will receive a notification once the funds are transferred to your account.</p>
        <p>Transaction Reference: <strong>{tx_ref}</strong></p>
        <p>Thank you for using our service!</p>
        
        <script>
            const txRef = "{tx_ref}";
            const socket = new WebSocket("ws://{settings.APP_ADDRESS.replace("http://", "").replace("https://", "")}/ws/wallet");
            socket.onopen = () => {{
                socket.send(JSON.stringify({{ tx_ref: txRef }}));
            }};
            socket.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                if (data.status === "success") {{
                    alert("Withdrawal successful! You will receive a notification soon.");
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
    await publish_flutter_event(data)
    return Response(
        status_code=status.HTTP_200_OK,
    )


@router.get("/flutterwave/get-banks", response_model=BankResponseSchema)
async def get_banks(
    flutterwave_client: Annotated[FlutterWaveClient, Depends(get_flutterwave_client)],
) -> BankResponseSchema:
    """
    Retrieve the list of banks from FlutterWave.

    Args:
        flutterwave_client (FlutterWaveClient): The payment gateway client for fetching bank details.

    Returns:
        BankResponseSchema: The response containing the list of banks.
    """
    flutterwave_response = await flutterwave_client.get_banks()
    banks = flutterwave_response.get("data", [])
    if not banks:
        request_logger.warning("No banks found in FlutterWave response.")
        return BankResponseSchema(banks=[])
    # Map the bank data to the BankSchema
    banks = [
        BankSchema(**bank)
        for bank in banks
        if "id" in bank and "name" in bank and "code" in bank
    ]
    return BankResponseSchema(banks=banks)


@router.get("/flutterwave/verify-bank")
async def verify_bank_details(
    flutterwave_client: Annotated[FlutterWaveClient, Depends(get_flutterwave_client)],
    data: Annotated[BankDetailsRequestSchema, Form()],
) -> BankDetailsSchema:
    """
    Verify bank details using FlutterWave.

    Args:
        flutterwave_client (FlutterWaveClient): The payment gateway client for verifying bank details.
        data (BankDetailsRequestSchema): The form data containing the bank code and account number.

    Returns:
        BankDetailsSchema: The response containing the verification status and message.

    Raises:
        BankVerificationError: If the bank verification fails.
    """
    verification_response = await flutterwave_client.verify_bank_details(
        bank_code=data.bank_code,
        account_number=data.account_number,
    )
    account_name: str = verification_response.get("data", {}).get("account_name", "")
    if not verification_response.get("status") == "success" or not account_name.strip():
        raise BankVerificationError(
            "Bank verification failed. Please check the bank details and try again."
        )
    return BankDetailsSchema(
        account_number=data.account_number,
        bank_code=data.bank_code,
        account_name=account_name,
    )


@router.post("/withdraw", response_class=RedirectResponse)
async def withdraw_from_wallet(
    user: Annotated[UserModel, Depends(get_current_active_user)],
    data: Annotated[WithdrawWalletSchema, Form()],
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
    transaction_db: Annotated[TransactionDB, Depends(get_transaction_db)],
    flutterwave_client: Annotated[FlutterWaveClient, Depends(get_flutterwave_client)],
    session: Annotated[AsyncClientSession, Depends(get_session)],
    request: Request,
):
    """
    Withdraw from the wallet for the current user.

    Args:
        user (UserModel): The currently authenticated user.
        data (WithdrawWalletSchema): The form data containing the amount to withdraw.
        wallet_db (WalletDB): The WalletDB instance for database operations.
        transaction_db (TransactionDB): The TransactionDB instance for transaction records.
        flutterwave_client (FlutterWaveClient): The payment gateway client for processing withdrawals.
        session (AsyncClientSession): The database session.
        request (Request): The incoming request object.

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

    try:
        # Verify the bank details
        verification_response = await flutterwave_client.verify_bank_details(
            bank_code=data.bank_code,
            account_number=data.account_number,
        )
        account_name: str = verification_response.get("data", {}).get(
            "account_name", ""
        )
        if (
            not verification_response.get("status") == "success"
            or not account_name.strip()
        ):
            raise BankVerificationError(
                "Bank verification failed. Please check the bank details and try again."
            )

        if not wallet.is_locked:
            await wallet_db.toggle_wallet_lock(
                user.id
            )  # Lock the wallet to prevent concurrent withdrawal operations
        async with await session.start_transaction(
            write_concern=WriteConcern("majority"), read_concern=ReadConcern("snapshot")
        ):
            # Implement withdrawal logic, via payment gateway before updating the wallet balance
            flutterwave_response = await flutterwave_client.initiate_transfer(
                user_id=str(user.id),
                amount=data.amount,
                bank_code=data.bank_code,
                account_number=data.account_number,
                currency=data.currency,
            )
            reference = flutterwave_response.get("data", {}).get("reference", "")
            now = datetime.now(tz=timezone.utc).isoformat()
            timestamp = flutterwave_response.get("created_at", now)
            if (
                not flutterwave_response.get("status") == "success"
                or not reference
                or not timestamp
            ):
                raise TransactionError("Withdrawal failed. Please try again later.")
            # Create a transaction record for the withdrawal
            transaction_record = TransactionModel(
                user_id=user.id,
                wallet_id=wallet.id,
                amount=data.amount,
                currency=data.currency,
                type=TransactionType.WITHDRAW.value,
                status=TransactionStatus.PENDING.value,
                reference=reference,
                timestamp=timestamp,
            )
            await transaction_db.create(
                transaction_record.model_dump(), session=session
            )
            redirect_url = request.url_for(
                "withdraw_success",
                tx_ref=reference,
            )
            return RedirectResponse(
                url=redirect_url,
                status_code=status.HTTP_303_SEE_OTHER,
            )
    except BankVerificationError or PaymentFailedError as e:
        await wallet_db.toggle_wallet_lock(
            user.id, lock=False
        )  # Unlock the wallet if an error occurs
        raise e
