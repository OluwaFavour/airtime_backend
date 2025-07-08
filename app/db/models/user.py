from bson import ObjectId
from typing import Optional, List, Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.config import database
from app.db.models.base import PyObjectId


class UserModel(BaseModel):
    id: Annotated[Optional[PyObjectId], Field(alias="_id")] = None
    email: Annotated[EmailStr, Field(description="User's email address")]
    hashed_password: Annotated[str, Field(description="Hashed password of the user")]
    is_active: Annotated[bool, Field(default=True, description="Is the user active?")]
    is_admin: Annotated[bool, Field(default=False, description="Is the user an admin?")]

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            ObjectId: str,
        },
        json_schema_extra={
            "example": {
                "email": "jdoe@example.com",
                "hashed_password": "hashed_password_example",
                "is_active": True,
                "is_admin": False,
            }
        },
    )


class UserCollection(BaseModel):
    users: List[UserModel]


user_collection = database.get_collection("users")
