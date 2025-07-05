from pydantic import BaseModel, Field, EmailStr, ConfigDict, AfterValidator
from typing import Optional, List, Annotated

from app.core.validators import validate_password


class UserRegistrationSchema(BaseModel):
    email: Annotated[EmailStr, Field(description="User's email address")]
    password: Annotated[
        str,
        Field(min_length=8, description="User's password"),
        AfterValidator(validate_password),
    ]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "johndoe@example.com", "password": "strongpassword123"}
        }
    )


class UserLoginSchema(BaseModel):
    email: Annotated[EmailStr, Field(description="User's email address")]
    password: Annotated[str, Field(min_length=8, description="User's password")]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "johndoe@example.com", "password": "strongpassword123"}
        }
    )


class TokenSchema(BaseModel):
    access_token: Annotated[str, Field(description="JWT access token")]
    token_type: Annotated[str, Field(default="bearer", description="Type of the token")]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
            }
        }
    )
