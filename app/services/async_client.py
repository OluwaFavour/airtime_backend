import asyncio
import httpx


class AsyncClient:
    """
    A class to manage asynchronous HTTP requests using httpx.AsyncClient.
    """

    def __init__(self):
        self.client = httpx.AsyncClient()

    async def get(
        self, url: str, max_retries: int = 3, retry_delay: float = 1.0, **kwargs
    ) -> httpx.Response:
        """
        Asynchronously sends a GET request to the specified URL.

        Args:
            url (str): The URL to send the GET request to.
            max_retries (int): The maximum number of retries for the request in case of failure.
            retry_delay (float): The delay in seconds between retries.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            httpx.Response: The response object from the GET request.
        Raises:
            httpx.RequestError: If the request fails after the specified number of retries.
        """
        for attempt in range(max_retries):
            try:
                response = await self.client.get(url, **kwargs)
                response.raise_for_status()  # Raise an error for bad responses
                return response
            except httpx.RequestError or httpx.HTTPStatusError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise httpx.RequestError(
                        f"Failed to fetch {url} after {max_retries} attempts"
                    ) from e

    async def post(
        self,
        url: str,
        data: dict = None,
        json: dict = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs,
    ) -> httpx.Response:
        """
        Asynchronously sends a POST request to the specified URL.

        Args:
            url (str): The URL to send the POST request to.
            data (dict): The form data to send in the POST request.
            json (dict): The JSON data to send in the POST request.
            max_retries (int): The maximum number of retries for the request in case of failure.
            retry_delay (float): The delay in seconds between retries.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            httpx.Response: The response object from the POST request.
        Raises:
            httpx.RequestError: If the request fails after the specified number of retries.
        """
        for attempt in range(max_retries):
            try:
                response = await self.client.post(url, data=data, json=json, **kwargs)
                response.raise_for_status()  # Raise an error for bad responses
                return response
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise httpx.RequestError(
                        f"Failed to post to {url} after {max_retries} attempts"
                    ) from e

    async def put(
        self,
        url: str,
        data: dict = None,
        json: dict = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs,
    ) -> httpx.Response:
        """
        Asynchronously sends a PUT request to the specified URL.
        Args:
            url (str): The URL to send the PUT request to.
            data (dict): The form data to send in the PUT request.
            json (dict): The JSON data to send in the PUT request.
            max_retries (int): The maximum number of retries for the request in case of failure.
            retry_delay (float): The delay in seconds between retries.
            **kwargs: Additional keyword arguments to pass to the request.
        Returns:
            httpx.Response: The response object from the PUT request.
        Raises:
            httpx.RequestError: If the request fails after the specified number of retries.
        """
        for attempt in range(max_retries):
            try:
                response = await self.client.put(url, data=data, json=json, **kwargs)
                response.raise_for_status()  # Raise an error for bad responses
                return response
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise httpx.RequestError(
                        f"Failed to put to {url} after {max_retries} attempts"
                    ) from e

    async def delete(
        self, url: str, max_retries: int = 3, retry_delay: float = 1.0, **kwargs
    ) -> httpx.Response:
        """
        Asynchronously sends a DELETE request to the specified URL.

        Args:
            url (str): The URL to send the DELETE request to.
            max_retries (int): The maximum number of retries for the request in case of failure.
            retry_delay (float): The delay in seconds between retries.
            **kwargs: Additional keyword arguments to pass to the request.

        Returns:
            httpx.Response: The response object from the DELETE request.
        Raises:
            httpx.RequestError: If the request fails after the specified number of retries.
        """
        for attempt in range(max_retries):
            try:
                response = await self.client.delete(url, **kwargs)
                response.raise_for_status()  # Raise an error for bad responses
                return response
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise httpx.RequestError(
                        f"Failed to delete {url} after {max_retries} attempts"
                    ) from e

    async def close(self):
        """
        Closes the AsyncClient instance and releases any resources.
        """
        await self.client.aclose()


# Create a global instance of AsyncClient for use in the application

async_request_client = AsyncClient()


def get_async_client() -> AsyncClient:
    """
    Dependency to get an instance of AsyncClient for making asynchronous HTTP requests.

    Returns:
        AsyncClient: An instance of AsyncClient.
    """
    return async_request_client
