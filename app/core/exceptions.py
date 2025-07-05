class TokenError(Exception):
    """
    Exception raised for errors related to authentication tokens.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise TokenError("Invalid or expired token.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"TokenError: {self.message}"
