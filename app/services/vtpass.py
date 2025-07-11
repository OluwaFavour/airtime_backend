from datetime import datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import httpx

from app.core.config import get_settings
from app.exceptions.types import AirtimePurchaseError
from app.services.async_client import get_async_client

settings = get_settings()


class VTPassClient:
    def __init__(
        self, api_key: str, public_key: str, secret_key: str, sandbox_mode: bool = True
    ):
        self.client = get_async_client()
        self.api_key = api_key
        self.public_key = public_key
        self.secret_key = secret_key
        self.base_url = (
            "https://vtpass.com/api"
            if not sandbox_mode
            else "https://sandbox.vtpass.com/api"
        )
        self.get_headers = {
            "api-key": self.api_key,
            "public-key": self.public_key,
        }
        self.post_headers = {
            "api-key": self.api_key,
            "secret-key": self.secret_key,
            "Content-Type": "application/json",
        }
        self.success_code = "000"
        self.requery_code = "099"

    def _generate_request_id(self, user_id: str) -> str:
        """
        Generates a unique request ID by combining the current timestamp (in Africa/Lagos timezone)
        formatted as 'YYYYMMDDHHMM' with the provided user ID.

        Args:
            user_id (str): The unique identifier of the user.

        Returns:
            str: A unique request ID string composed of the timestamp and user ID.
        """
        african_timezone = ZoneInfo("Africa/Lagos")
        now = datetime.now(tz=timezone.utc).astimezone(african_timezone)
        timestamp = now.strftime("%Y%m%d%H%M")
        return f"{timestamp}{user_id}"

    async def get_services(self) -> Dict[str, Any]:
        """
        Asynchronously retrieves a list of available services from the VTpass API.

        Returns:
            Dict[str, Any]: A dictionary containing the JSON response with service details.

        Raises:
            httpx.HTTPError: If the HTTP request fails.
        """
        url = f"{self.base_url}/services?identifier=airtime"
        response = await self.client.get(url, headers=self.get_headers)
        return response.json()

    async def buy_airtime(
        self,
        user_id: str,
        service_id: str,
        amount: float,
        phone_number: str,
    ) -> Dict[str, Any]:
        """
        Asynchronously purchases airtime for a given user and phone number using the specified service.

        Args:
            user_id (str): The unique identifier of the user making the purchase.
            service_id (str): The identifier of the airtime service provider.
            amount (float): The amount of airtime to purchase.
            phone_number (str): The recipient's phone number.

        Returns:
            Dict[str, Any]: The response from the airtime purchase API.

        Raises:
            AirtimePurchaseError: If there is an error during the airtime purchase process.
        """
        url = f"{self.base_url}/pay"
        request_id = self._generate_request_id(user_id)
        payload = {
            "serviceID": service_id,
            "amount": amount,
            "phone": phone_number,
            "request_id": request_id,
        }
        try:
            response = await self.client.post(
                url, json=payload, headers=self.post_headers
            )
            return response.json()
        except httpx.RequestError or httpx.HTTPStatusError as e:
            raise AirtimePurchaseError(
                f"Error buying airtime: {str(e)}", user_id=user_id, unlock_wallet=True
            )

    async def query_transaction(
        self,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Asynchronously queries the status of a transaction using the provided request ID.

        Args:
            request_id (str): The unique identifier of the transaction to be queried.

        Returns:
            Dict[str, Any]: The JSON response from the API containing the transaction status and related information.

        Raises:
            httpx.HTTPError: If the HTTP request fails.
        """
        url = f"{self.base_url}/requery"
        payload = {
            "request_id": request_id,
        }
        response = await self.client.post(url, json=payload, headers=self.post_headers)
        return response.json()

    def process_response(
        self,
        response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Processes the response from a VTpass API call and returns a standardized result.

        Args:
            response (Dict[str, Any]): The response dictionary from the VTpass API.

        Returns:
            Dict[str, Any]: A dictionary containing the transaction status, message, and request ID.
                - status (str): One of "success", "pending", "failed", "requery", or "error".
                - message (str): A descriptive message about the transaction status.
                - request_id (str or None): The unique identifier for the transaction request.

        The method interprets the response code and transaction status to determine the overall
        result of the transaction, providing a consistent structure for downstream processing.
        """
        code: Optional[str] = response.get("code")
        request_id: Optional[str] = response.get("requestId")
        response_description: Optional[str] = response.get("response_description")
        if code == self.success_code:
            response_status: Optional[str] = (
                response.get("content", {}).get("transactions", {}).get("status")
            )
            if response_status == "success":
                return {
                    "status": "success",
                    "message": response_description or "Transaction successful",
                    "request_id": request_id,
                }
            elif response_status == "pending" or response_status == "initiated":
                return {
                    "status": "pending",
                    "message": response_description or "Transaction is pending",
                    "request_id": request_id,
                }
            else:
                return {
                    "status": "failed",
                    "message": response_description or "Transaction failed",
                    "request_id": request_id,
                }
        elif code == self.requery_code:
            return {
                "status": "requery",
                "message": response_description or "Transaction is being re-queried",
                "request_id": request_id,
            }
        else:
            return {
                "status": "error",
                "message": response_description or "An error occurred",
                "request_id": request_id,
            }


vtpass_client = VTPassClient(
    settings.VTPASS_API_KEY,
    settings.VTPASS_PUBLIC_KEY,
    settings.VTPASS_SECRET_KEY,
    sandbox_mode=settings.VTPASS_SANDBOX_MODE,
)


def get_vtpass_client() -> VTPassClient:
    """
    Returns an instance of the VTPassClient.

    This function provides access to the pre-configured VTPassClient instance,
    which can be used to interact with the VTpass API for various services.

    Returns:
        VTPassClient: The initialized VTpass client instance.
    """
    return vtpass_client
