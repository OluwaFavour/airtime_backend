class CredentialError(Exception):
    """
    Exception raised for errors related to user credentials.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise CredentialError("Invalid username or password.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"CredentialError: {self.message}"


class TokenError(CredentialError):
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


class InactiveObjectError(Exception):
    """
    Exception raised when an object (e.g., user) is inactive.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise InactiveObjectError("User account is inactive.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"InactiveObjectError: {self.message}"


class ObjectNotFoundError(Exception):
    """
    Exception raised when an object is not found in the database.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise ObjectNotFoundError("User not found.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"ObjectNotFoundError: {self.message}"


class ObjectAlreadyExistsError(Exception):
    """
    Exception raised when an object already exists in the database.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise ObjectAlreadyExistsError("User with this email already exists.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"ObjectAlreadyExistsError: {self.message}"
