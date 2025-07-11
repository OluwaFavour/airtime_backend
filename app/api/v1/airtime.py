from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Form

import httpx
from pymongo import WriteConcern
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.read_concern import ReadConcern

from app.api.dependencies import (
    get_current_active_user,
    get_session,
    get_transaction_db,
    get_wallet_db,
)
from app.db.crud.transactions import TransactionDB
from app.db.crud.wallet import UpdateMode, WalletDB
from app.db.models.user import UserModel
from app.db.models.wallet import TransactionModel, TransactionStatus, TransactionType
from app.exceptions.types import AirtimePurchaseError
from app.schemas.airtime import (
    AirtimePurchaseSchema,
    AirtimeServiceListSchema,
    AirtimeServiceSchema,
)
from app.services.vtpass import VTPassClient, get_vtpass_client


router = APIRouter()


@router.get("/airtime/services", response_model=AirtimeServiceListSchema)
async def get_airtime_services(
    vtpass_client: Annotated[VTPassClient, Depends(get_vtpass_client)],
):
    """Retrieve available airtime services from VTPass."""
    services = await vtpass_client.get_services()
    response = AirtimeServiceListSchema(
        content=[
            AirtimeServiceSchema(
                serviceID=service["serviceID"],
                name=service["name"],
                minimum_amount=service["minimum_amount"],
                maximum_amount=service["maximum_amount"],
                image=service.get("image"),
            )
            for service in services.get("content", [])
        ]
    )
    return response


@router.post("/airtime/purchase", response_model=TransactionModel)
async def purchase_airtime(
    user: Annotated[UserModel, Depends(get_current_active_user)],
    data: Annotated[AirtimePurchaseSchema, Form()],
    vtpass_client: Annotated[VTPassClient, Depends(get_vtpass_client)],
    transaction_db: Annotated[TransactionDB, Depends(get_transaction_db)],
    wallet_db: Annotated[WalletDB, Depends(get_wallet_db)],
    session: Annotated[AsyncClientSession, Depends(get_session)],
):
    """Purchase airtime for a user.
    Args:
        user (UserModel): The current active user.
        data (AirtimePurchaseSchema): The airtime purchase details.
        vtpass_client (VTPassClient): The VTPass client for making API calls.
        transaction_db (TransactionDB): The database for transaction operations.
        wallet_db (WalletDB): The database for wallet operations.
        session (AsyncClientSession): The MongoDB session.
    Returns:
        TransactionModel: The transaction record for the airtime purchase.
    """
    # Validate the service ID
    try:
        services_response = await vtpass_client.get_services()
        services = [
            service["serviceID"] for service in services_response.get("content", [])
        ]
        if data.service_id not in services:
            raise AirtimePurchaseError(
                f"Invalid service ID: {data.service_id}. Available services: {', '.join(services)}",
                user_id=user.id,
            )
    except httpx.RequestError or httpx.HTTPStatusError as e:
        raise AirtimePurchaseError(
            f"Error fetching services: {str(e)}", user_id=user.id
        )

    # Validate the user's wallet balance
    wallet = await wallet_db.get_by_user_id(user.id)
    if not wallet or wallet.balance < data.amount:
        raise AirtimePurchaseError("Insufficient wallet balance for airtime purchase.")

    # Lock the wallet to prevent concurrent modifications
    await wallet_db.toggle_wallet_lock(user_id=user.id, lock=True)
    try:
        async with await session.start_transaction(
            write_concern=WriteConcern("majority"), read_concern=ReadConcern("snapshot")
        ):
            # Purchase airtime using VTPass client
            response = await vtpass_client.buy_airtime(
                user_id=user.id,
                service_id=data.service_id,
                amount=data.amount,
                phone_number=data.phone_number,
            )
            processed_response = vtpass_client.process_response(response)
            transaction_record = TransactionModel(
                user_id=user.id,
                wallet_id=wallet.id,
                amount=data.amount,
                currency="NGN",
                type=TransactionType.AIRTIME_PURCHASE.value,
                status=TransactionStatus.PENDING.value,
                reference=processed_response.get("request_id"),
                timestamp=datetime.now(tz=timezone.utc),
            )
            if processed_response.get("status") in ["failed", "error"]:
                transaction_record.status = TransactionStatus.FAILED.value
                await transaction_db.create(
                    transaction_record.model_dump(), session=session
                )
                raise AirtimePurchaseError(
                    f"Airtime purchase failed: {processed_response.get('message')}",
                    user_id=user.id,
                    unlock_wallet=True,
                )
            elif processed_response.get("status") in ["pending", "requery"]:
                # TODO: Handle pending or requery status
                transaction_record.status = TransactionStatus.PENDING.value
                await transaction_db.create(
                    transaction_record.model_dump(), session=session
                )
            elif processed_response.get("status") == "success":
                # Update wallet balance
                await wallet_db.update_balance(
                    user_id=user.id,
                    amount=data.amount,
                    mode=UpdateMode.SUBTRACT,
                    session=session,
                )
                transaction_record.status = TransactionStatus.SUCCESS.value
                transaction = await transaction_db.create(
                    transaction_record.model_dump(), session=session
                )
                return transaction
            else:
                raise AirtimePurchaseError(
                    "Unexpected response status from airtime purchase.",
                    user_id=user.id,
                    unlock_wallet=True,
                )
    except AirtimePurchaseError as e:
        if e.unlock_wallet:
            await wallet_db.toggle_wallet_lock(user_id=e.user_id, lock=False)
        raise e
