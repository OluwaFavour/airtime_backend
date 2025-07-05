import re

from app.core.constants import PASSWORD_REGEX


def validate_password(password: str) -> str:
    """
    Validates the strength of a password based on specific criteria.

    Args:
        password (str): The password to validate.

    Returns:
        bool: True if the password meets the criteria, False otherwise.
    """
    match = PASSWORD_REGEX.match(password)
    if not match:
        raise ValueError(
            "Password must be at least 8 characters long, "
            "contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character."
        )
    return password
