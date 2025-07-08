from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from pymongo import WriteConcern
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.read_concern import ReadConcern

from app.api.dependencies import (
    transaction_db,
    wallet_db,
)
from app.core.config import get_settings, request_logger
from app.db.crud.wallet import UpdateMode
from app.db.models.wallet import TransactionModel, TransactionStatus, WalletModel
from app.db.sessions import get_session_context
from app.exceptions.types import PaymentGatewayError
from app.services.async_client import get_async_client
from app.services.redis import publisher as websocket_publisher


settings = get_settings()


class FlutterWaveClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.flutterwave.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.client = get_async_client()
        self.payment_options = settings.FLUTTERWAVE_PAYMENT_OPTIONS

    @classmethod
    def create_customer(
        cls, email: str, name: Optional[str] = None, phone_number: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Creates a customer in Flutterwave.

        Args:
            email (str): The customer's email address.
            name (Optional[str]): The customer's name. Defaults to None.
            phone_number (Optional[str]): The customer's phone number. Defaults to None.

        Returns:
            Dict[str, str]: A dictionary containing the customer name and email.
        """
        data = {
            "email": email,
        }
        if name:
            data["name"] = name
        if phone_number:
            data["phone_number"] = phone_number
        return data

    async def initiate_payment(
        self,
        user_id: str,
        email: str,
        amount: float,
        currency: str = "NGN",
        name: Optional[str] = None,
        phone_number: Optional[str] = None,
        customizations: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Initiates a payment request to Flutterwave.

        Args:
            id (str): The customer's unique identifier.
            email (str): The customer's email address.
            amount (float): The amount to be charged.
            currency (str): The currency of the transaction, default is "NGN".
            name (Optional[str]): The customer's name. Defaults to None.
            phone_number (Optional[str]): The customer's phone number. Defaults to None.
            customizations (Optional[Dict[str, Any]]): Additional customizations for the payment request.
            These can only include `title`, and `logo` keys.

        Returns:
            Dict[str, str]: The response from the Flutterwave API.
        """
        customer = self.create_customer(email, name, phone_number)
        url = f"{self.base_url}/payments"
        now = datetime.now(tz=timezone.utc)
        timestamp = now.strftime("%Y%m%d%H%M%S")
        link_expiry = now + timedelta(minutes=settings.FLUTTERWAVE_LINK_EXPIRY_MINUTES)
        tx_ref = f"tx_ref-{user_id}-{uuid4()}-{timestamp}"
        payload = {
            "tx_ref": tx_ref,
            "amount": amount,
            "currency": currency,
            "redirect_url": f"{settings.APP_ADDRESS}{settings.FLUTTERWAVE_REDIRECT_URL}",
            "customer": customer,
            "link_expiration": link_expiry.isoformat(),
            "payment_options": ", ".join(self.payment_options),
            "max_retry_attempt": 3,
            "meta": {
                "user_id": user_id,
            },
            "configuration": {
                "session_duration": settings.FLUTTERWAVE_SESSION_DURATION_MINUTES,
            },
        }
        if customizations:
            payload["customizations"] = customizations
        response = await self.client.post(
            url,
            json=payload,
            headers=self.headers,
            max_retries=3,
        )
        data = response.json()
        data["tx_ref"] = tx_ref
        data["created_at"] = now.isoformat()
        return data

    async def verify_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Verifies a transaction with Flutterwave.

        Args:
            transaction_id (str): The unique identifier of the transaction to verify.

        Returns:
            Dict[str, Any]: The response from the Flutterwave API containing transaction details.
        """
        url = f"{self.base_url}/transactions/{transaction_id}/verify"
        response = await self.client.get(
            url,
            headers=self.headers,
        )
        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to verify transaction {transaction_id}: {response.text}"
            )
        return response.json()

    def verify_webhook_signature(self, signature: str) -> bool:
        """
        Verifies the webhook signature from Flutterwave.

        Args:
            signature (str): The signature to verify.

        Returns:
            bool: True if the signature is valid, False otherwise.
        """
        expected_signature = settings.FLUTTERWAVE_WEBHOOK_HASH
        return signature == expected_signature

    async def process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._validate_payload(data):
            return self._response("error", "Missing required fields in webhook.")

        if not self.verify_webhook_signature(data["signature"]):
            return self._response("error", "Invalid webhook signature.")

        if data["event.type"] not in self._valid_event_types():
            return self._response("ignored", "Unsupported event type.")

        tx_ref = data["txRef"]
        flw_tx_id = data["id"]
        flw_status = data["status"]
        user_id = data.get("meta_data", {}).get("user_id")

        try:
            async with get_session_context() as session:
                async with await session.start_transaction(
                    write_concern=WriteConcern("majority"),
                    read_concern=ReadConcern("snapshot"),
                ):
                    transaction = await transaction_db.get_by_reference(
                        tx_ref, session=session
                    )
                    wallet = await wallet_db.get_by_user_id(
                        user_id=user_id, session=session
                    )

                    if not transaction:
                        await self._unlock_wallet_if_locked(wallet, session)
                        return self._response("error", "Transaction not found.")

                    if transaction.status == TransactionStatus.SUCCESS.value:
                        return self._response(
                            "skipped", "Transaction already processed."
                        )

                    if transaction.status != TransactionStatus.PENDING.value:
                        return self._response(
                            "error", f"Invalid transaction status: {transaction.status}"
                        )

                    if flw_status == "successful":
                        return await self._handle_success(
                            transaction, flw_tx_id, session
                        )
                    else:
                        return await self._handle_failure(transaction, wallet, session)

        except Exception as e:
            # Log, notify admin, or push to alerting system
            request_logger.error(f"Webhook processing failed: {e}")
            return self._response("error", "Webhook processing failed unexpectedly.")

    def _validate_payload(self, data: dict) -> bool:
        required = {"txRef", "status", "id", "event.type", "signature", "meta_data"}
        return (
            bool(data)
            and required.issubset(data)
            and isinstance(data.get("meta_data"), dict)
            and "user_id" in data["meta_data"]
        )

    def _valid_event_types(self) -> list[str]:
        return [f"{opt.upper()}_TRANSACTION" for opt in self.payment_options]

    def _response(self, status: str, message: str) -> dict:
        request_logger.info(f"Webhook response: {status} - {message}")
        return {"status": status, "message": message}

    async def _unlock_wallet_if_locked(
        self, wallet: WalletModel, session: AsyncClientSession
    ):
        if wallet and wallet.is_locked:
            await wallet_db.toggle_wallet_lock(wallet.user_id, session=session)

    async def _handle_success(
        self,
        transaction: TransactionModel,
        flw_tx_id: str,
        session: AsyncClientSession,
    ):
        verify = await self.verify_transaction(transaction_id=flw_tx_id)
        if (
            verify["status"] == "success"
            and verify["data"]["amount"] >= transaction.amount
            and verify["data"]["currency"] == transaction.currency
        ):
            actual = verify["data"]["amount"]

            await transaction_db.update(
                transaction.id,
                {"status": TransactionStatus.SUCCESS.value},
                session=session,
            )

            updated_wallet = await wallet_db.update_balance(
                transaction.user_id, amount=actual, mode=UpdateMode.ADD, session=session
            )

            await self._unlock_wallet_if_locked(updated_wallet, session)

            await websocket_publisher.publish_message(
                transaction.reference,
                {
                    "status": "success",
                    "message": "Wallet funded successfully.",
                    "tx_ref": transaction.reference,
                    "user_id": transaction.user_id,
                    "amount": actual,
                    "currency": transaction.currency,
                },
            )

            return self._response("success", "Wallet funded successfully.")

        return self._response("error", "Verification mismatch or failed.")

    async def _handle_failure(
        self,
        transaction: TransactionModel,
        wallet: WalletModel,
        session: AsyncClientSession,
    ):
        await transaction_db.update(
            transaction.id, {"status": TransactionStatus.FAILED.value}, session=session
        )

        await self._unlock_wallet_if_locked(wallet, session)

        await websocket_publisher.publish_message(
            transaction.reference,
            {
                "status": "failed",
                "message": "Payment failed or cancelled.",
                "tx_ref": transaction.reference,
                "user_id": transaction.user_id,
                "amount": transaction.amount,
                "currency": transaction.currency,
            },
        )

        return self._response("failed", "Payment failed or cancelled.")


flutterwave_client = FlutterWaveClient(settings.FLUTTERWAVE_SECRET_KEY)


def get_flutterwave_client() -> FlutterWaveClient:
    """
    Dependency to get an instance of FlutterWaveClient for making payment requests.

    Returns:
        FlutterWaveClient: An instance of FlutterWaveClient.
    """
    return flutterwave_client
