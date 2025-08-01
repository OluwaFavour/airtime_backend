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

    def __init__(self, message: str, status_code: int = 404):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def __str__(self):
        return f"ObjectNotFoundError: {self.message}"


class WalletAwareError(Exception):
    """
    Exception raised for errors that are related to wallet operations and are user-specific.

    Attributes:
        message (str): Human-readable message describing the error.
        user_id (str): Identifier of the user associated with the error.
        unlock_wallet (bool): Indicates whether the wallet should be unlocked as a result of this error. Defaults to False.
    """

    def __init__(self, message: str, user_id: str, unlock_wallet: bool = False):
        self.message = message
        self.user_id = user_id
        self.unlock_wallet = unlock_wallet
        super().__init__(message)


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


class WalletError(Exception):
    """
    Exception raised for errors related to wallet operations.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise WalletError("Insufficient funds in the wallet.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"WalletError: {self.message}"


class TransactionError(Exception):
    """
    Exception raised for errors related to transaction operations.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise TransactionError("Transaction failed due to insufficient funds.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"TransactionError: {self.message}"


class DatabaseError(Exception):
    """
    Exception raised for errors related to database operations.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise DatabaseError("Database connection failed.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"DatabaseError: {self.message}"


class PaymentFailedError(WalletAwareError):
    """
    Exception raised when a payment fails.
    Attributes:
        message (str): Explanation of the error.
        user_id (str): Identifier of the user associated with the error.
        unlock_wallet (bool): Indicates whether the wallet should be unlocked as a result of this error. Defaults to False.
    Example:
        raise PaymentFailedError("Payment processing failed due to insufficient funds.")
    """

    def __init__(self, message: str, user_id: str, unlock_wallet: bool = False):
        super().__init__(message, user_id, unlock_wallet)

    def __str__(self):
        return f"PaymentFailedError: {self.message}"


class BankVerificationError(Exception):
    """
    Exception raised when bank verification fails.
    Attributes:
        message (str): Explanation of the error.
    Example:
        raise BankVerificationError("Bank verification failed due to invalid details.")
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"BankVerificationError: {self.message}"


class AirtimePurchaseError(WalletAwareError):
    """
    Exception raised when an error occurs during airtime purchase.
    Attributes:
        message (str): Explanation of the error.
        user_id (str): Identifier of the user associated with the error.
        unlock_wallet (bool): Indicates whether the wallet should be unlocked as a result of this error. Defaults to False.
    Example:
        raise AirtimePurchaseError("Airtime purchase failed due to insufficient funds.", user_id="12345")
    """

    def __init__(self, message: str, user_id: str, unlock_wallet: bool = False):
        super().__init__(message, user_id, unlock_wallet)
