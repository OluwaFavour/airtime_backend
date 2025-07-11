from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
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
from app.exceptions.types import (
    BankVerificationError,
    PaymentFailedError,
)
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
        self.payment_event_types = [
            f"{opt.upper()}_TRANSACTION" for opt in self.payment_options
        ]
        self.transfer_event_types = ["Transfer"]

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

    def _generate_tx_ref(self, user_id: str) -> str:
        """
        Generates a unique transaction reference.

        Args:
            user_id (str): The user's unique identifier.

        Returns:
            str: A unique transaction reference string.
        """
        now = datetime.now(tz=timezone.utc)
        timestamp = now.strftime("%Y%m%d%H%M%S")
        return f"tx_ref-{user_id}-{timestamp}"

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
        link_expiry = now + timedelta(minutes=settings.FLUTTERWAVE_LINK_EXPIRY_MINUTES)
        tx_ref = self._generate_tx_ref(user_id)
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
        try:
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
        except httpx.RequestError or httpx.HTTPStatusError as e:
            raise PaymentFailedError(
                f"Failed to initiate payment: {e}", user_id=user_id, unlock_wallet=True
            ) from e

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
        return response.json()

    async def verify_bank_details(
        self, bank_code: str, account_number: str
    ) -> Dict[str, Any]:
        """
        Verifies bank details with Flutterwave.

        Args:
            bank_code (str): The bank code to verify.
            account_number (str): The account number to verify.

        Returns:
            Dict[str, Any]: The response from the Flutterwave API containing verification details.
        """
        url = f"{self.base_url}/accounts/resolve"
        payload = {
            "account_number": account_number,
            "account_bank": bank_code,
        }
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self.headers,
                max_retries=3,
            )
            return response.json()
        except httpx.RequestError or httpx.HTTPStatusError as e:
            raise BankVerificationError(f"Failed to verify bank details: {e}") from e

    async def get_banks(self, country: str = "NG") -> Dict[str, Any]:
        """
        Retrieves a list of banks for a given country from Flutterwave.

        Args:
            country (str): The country code for which to retrieve banks. Default is "NG" (Nigeria).

        Returns:
            Dict[str, Any]: The response from the Flutterwave API containing the list of banks.
        """
        url = f"{self.base_url}/banks/{country}"
        response = await self.client.get(
            url,
            headers=self.headers,
            max_retries=3,
        )
        return response.json()

    async def initiate_transfer(
        self,
        user_id: str,
        bank_code: str,
        account_number: str,
        amount: float,
        currency: str = "NGN",
    ) -> Dict[str, Any]:
        """
        Initiates a transfer request to Flutterwave.

        Args:
            user_id (str): The user's unique identifier.
            bank_code (str): The bank code for the transfer.
            account_number (str): The recipient's account number.
            amount (float): The amount to be transferred.
            currency (str): The currency of the transfer, default is "NGN".

        Returns:
            Dict[str, Any]: The response from the Flutterwave API containing transfer details.
        """
        url = f"{self.base_url}/transfers"
        tx_ref = self._generate_tx_ref(user_id)
        payload = {
            "reference": tx_ref,
            "amount": amount,
            "currency": currency,
            "account_bank": bank_code,
            "account_number": account_number,
            "meta": {
                "user_id": user_id,
            },
            "narration": f"Transfer to {account_number} from Airtime Backend",
        }
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self.headers,
                max_retries=3,
            )
            data = response.json()
            data["created_at"] = datetime.now(tz=timezone.utc).isoformat()
            return data
        except httpx.RequestError or httpx.HTTPStatusError as e:
            raise PaymentFailedError(
                f"Failed to initiate transfer: {e}", user_id=user_id, unlock_wallet=True
            ) from e

    async def handle_payment_webhook(
        self, data: Dict[str, Any], session: Optional[AsyncClientSession] = None
    ) -> Dict[str, Any]:
        """
        Handles incoming payment webhook data by processing it with the appropriate session context.

        Args:
            data (Dict[str, Any]): The webhook payload containing payment information.
            session (Optional[AsyncClientSession], optional): An existing asynchronous database session. If not provided, a new session context will be created.

        Returns:
            Dict[str, Any]: The result of processing the payment webhook.

        Raises:
            Any exceptions raised by the underlying _payment_webhook_processor method.
        """
        if not session:
            async with get_session_context() as session:
                return await self._payment_webhook_processor(data, session)
        return await self._payment_webhook_processor(data, session)

    async def _payment_webhook_processor(
        self, data: Dict[str, Any], session: AsyncClientSession
    ) -> Dict[str, Any]:
        """
        Processes payment webhook data and updates transaction and wallet records accordingly.
        Args:
            data (Dict[str, Any]): The webhook payload containing transaction details.
            session (AsyncClientSession): The asynchronous database session.
        Returns:
            Dict[str, Any]: A response dictionary indicating the result of the processing.
        Workflow:
            - Retrieves the transaction and wallet based on the provided data.
            - If the transaction is not found, unlocks the wallet (if locked) and returns an error response.
            - If the transaction has already been processed successfully, returns a skipped response.
            - If the transaction status is not pending, returns an error response.
            - If the payment status is "successful", handles the success logic.
            - Otherwise, handles the failure logic.
        """
        tx_ref = data["txRef"]
        flw_tx_id = data["id"]
        flw_status = data["status"]
        user_id = data.get("meta_data", {}).get("user_id")
        transaction = await transaction_db.get_by_reference(tx_ref, session=session)
        wallet = await wallet_db.get_by_user_id(user_id=user_id, session=session)

        if not transaction:
            await self._unlock_wallet_if_locked(wallet, session)
            return self._response("error", "Transaction not found.")

        if transaction.status == TransactionStatus.SUCCESS.value:
            return self._response("skipped", "Transaction already processed.")

        if transaction.status == TransactionStatus.FAILED.value:
            return self._response("skipped", "Transaction already failed.")

        if transaction.status != TransactionStatus.PENDING.value:
            return self._response(
                "error", f"Invalid transaction status: {transaction.status}"
            )

        if flw_status == "successful":
            return await self._handle_payment_success(transaction, flw_tx_id, session)
        else:
            return await self._handle_payment_failure(transaction, wallet, session)

    async def handle_transfer_webhook(
        self, data: Dict[str, Any], session: Optional[AsyncClientSession] = None
    ) -> Dict[str, Any]:
        """
        Handles incoming transfer webhook data by processing it with the appropriate session context.

        Args:
            data (Dict[str, Any]): The webhook payload containing transfer information.
            session (Optional[AsyncClientSession], optional): An existing asynchronous database session. If not provided, a new session context will be created.

        Returns:
            Dict[str, Any]: The result of processing the transfer webhook.

        Raises:
            Any exceptions raised by the underlying _transfer_webhook_processor method.
        """
        if not session:
            async with get_session_context() as session:
                return await self._transfer_webhook_processor(data, session)
        return await self._transfer_webhook_processor(data, session)

    async def _transfer_webhook_processor(
        self, data: Dict[str, Any], session: AsyncClientSession
    ) -> Dict[str, Any]:
        """
        Processes a webhook callback for a transfer transaction.
        This asynchronous method handles the processing of a transfer webhook event by:
        - Retrieving the transaction and wallet based on the provided webhook data.
        - Validating the transaction status and ensuring it is in a pending state.
        - Handling successful or failed transfer events by invoking the appropriate handler.
        - Unlocking the wallet if the transaction is not found.
        Args:
            data (Dict[str, Any]): The webhook payload containing transaction details.
            session (AsyncClientSession): The asynchronous database session.
        Returns:
            Dict[str, Any]: A response dictionary indicating the result of the webhook processing.
        """
        tx_ref = data["data"]["reference"]
        flw_status = data["data"]["status"]
        user_id = data["data"]["meta"].get("user_id")
        transaction = await transaction_db.get_by_reference(tx_ref, session=session)
        wallet = await wallet_db.get_by_user_id(user_id=user_id, session=session)

        if not transaction:
            await self._unlock_wallet_if_locked(wallet, session)
            return self._response("error", "Transaction not found.")

        if transaction.status == TransactionStatus.SUCCESS.value:
            return self._response("skipped", "Transaction already processed.")

        if transaction.status == TransactionStatus.FAILED.value:
            return self._response("skipped", "Transaction already failed.")

        if transaction.status != TransactionStatus.PENDING.value:
            return self._response(
                "error", f"Invalid transaction status: {transaction.status}"
            )

        if flw_status == "SUCCESSFUL":
            return await self._handle_transfer_success(transaction, session)
        else:
            return await self._handle_transfer_failure(transaction, wallet, session)

    async def _handle_transfer_success(
        self,
        transaction: TransactionModel,
        session: AsyncClientSession,
    ) -> Dict[str, Any]:
        """
        Handles the successful transfer of funds by updating the transaction and wallet records.

        Args:
            transaction (TransactionModel): The transaction model instance.
            session (AsyncClientSession): The asynchronous database session.

        Returns:
            Dict[str, Any]: A response dictionary indicating the success of the operation.
        """
        await transaction_db.update(
            transaction.id, {"status": TransactionStatus.SUCCESS.value}, session=session
        )

        updated_wallet = await wallet_db.update_balance(
            transaction.user_id,
            amount=transaction.amount,
            mode=UpdateMode.SUBTRACT,
            session=session,
        )

        await self._unlock_wallet_if_locked(updated_wallet, session)

        await websocket_publisher.publish_message(
            transaction.reference,
            {
                "status": "success",
                "message": "Transfer successful.",
                "tx_ref": transaction.reference,
                "user_id": transaction.user_id,
                "amount": transaction.amount,
                "currency": transaction.currency,
            },
        )

        return self._response("success", "Transfer successful.")

    async def _handle_transfer_failure(
        self,
        transaction: TransactionModel,
        wallet: WalletModel,
        session: AsyncClientSession,
    ) -> Dict[str, Any]:
        """
        Handles the failure of a transfer by updating the transaction status and unlocking the wallet if necessary.

        Args:
            transaction (TransactionModel): The transaction model instance.
            wallet (WalletModel): The wallet model instance.
            session (AsyncClientSession): The asynchronous database session.

        Returns:
            Dict[str, Any]: A response dictionary indicating the failure of the operation.
        """
        await transaction_db.update(
            transaction.id, {"status": TransactionStatus.FAILED.value}, session=session
        )

        await self._unlock_wallet_if_locked(wallet, session)

        # TODO: Retry transfer logic

        await websocket_publisher.publish_message(
            transaction.reference,
            {
                "status": "failed",
                "message": "Transfer failed or cancelled.",
                "tx_ref": transaction.reference,
                "user_id": transaction.user_id,
                "amount": transaction.amount,
                "currency": transaction.currency,
            },
        )

        return self._response("failed", "Transfer failed or cancelled.")

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
            return self._response("error", "Missing required fields in webhook.", data)

        if not self.verify_webhook_signature(data["signature"]):
            return self._response("error", "Invalid webhook signature.")

        if data["event.type"] not in self._valid_event_types():
            return self._response("ignored", "Unsupported event type.")

        event_type_handlers = {}
        for event_type in self._valid_event_types():
            if "_TRANSACTION" in event_type:
                event_type_handlers[event_type] = self.handle_payment_webhook
            elif event_type == "Transfer":
                event_type_handlers[event_type] = self.handle_transfer_webhook

        try:
            async with get_session_context() as session:
                async with await session.start_transaction(
                    write_concern=WriteConcern("majority"),
                    read_concern=ReadConcern("snapshot"),
                ):
                    handler = event_type_handlers.get(data["event.type"])
                    if handler:
                        return await handler(data, session)
                    else:
                        return self._response(
                            "ignored", "No handler for this event type."
                        )

        except Exception as e:
            # Log, notify admin, or push to alerting system
            request_logger.error(f"Webhook processing failed: {e}")
            return self._response("error", "Webhook processing failed unexpectedly.")

    def _validate_payload(self, data: dict) -> bool:
        event_type = data.get("event.type")
        if not event_type or not isinstance(event_type, str):
            return False
        if event_type in self.payment_event_types:
            required = {"txRef", "status", "id", "signature", "meta_data"}
            return (
                bool(data)
                and required.issubset(data)
                and isinstance(data.get("meta_data"), dict)
                and "user_id" in data["meta_data"]
            )
        elif event_type in self.transfer_event_types:
            data: Optional[Dict[str, Any]] = data.get("data", {})
            if not data:
                return False
            required = {"id", "status", "amount", "currency", "reference", "meta"}
            return (
                bool(data)
                and required.issubset(data)
                and isinstance(data.get("meta"), dict)
                and "user_id" in data["meta"]
            )

    def _valid_event_types(self) -> list[str]:
        """
        Returns a list of valid event types that this client can handle.

        Returns:
            list[str]: A list of valid event types.
        """
        return self.payment_event_types + self.transfer_event_types

    def _response(
        self, status: str, message: str, data: Optional[Dict[str, Any]] = None
    ) -> dict:
        request_logger.info(f"Webhook response: {status} - {message}")
        response = {"status": status, "message": message}
        if data:
            response["data"] = data
        return response

    async def _unlock_wallet_if_locked(
        self, wallet: WalletModel, session: AsyncClientSession
    ):
        await wallet_db.toggle_wallet_lock(
            user_id=wallet.user_id, lock=False, session=session
        )

    async def _handle_payment_success(
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

    async def _handle_payment_failure(
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
