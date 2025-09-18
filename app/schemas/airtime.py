from typing import Annotated, List, Optional
from pydantic import AfterValidator, BaseModel, ConfigDict, Field
import phonenumbers


def validate_phone_number(v: str) -> str:
    """
    Validate the phone number format.
    Args:
        cls: The class of the model.
        v: The phone number to validate.
    Returns:
        str: The validated phone number.
    Raises:
        ValueError: If the phone number is invalid.
    """
    try:
        parsed_number = phonenumbers.parse(v, "NG")
        if not phonenumbers.is_valid_number(parsed_number):
            raise ValueError("Invalid phone number format.")
        return phonenumbers.format_number(
            parsed_number, phonenumbers.PhoneNumberFormat.NATIONAL
        ).replace(" ", "")
    except phonenumbers.NumberParseException as e:
        raise ValueError(f"Invalid phone number: {e}")


class AirtimePurchaseSchema(BaseModel):
    phone_number: Annotated[
        str,
        Field(description="The phone number to which the airtime will be sent."),
        AfterValidator(
            validate_phone_number,
        ),
    ]
    amount: Annotated[
        float, Field(gt=0, description="The amount of airtime to purchase.")
    ]
    service_id: Annotated[
        str,
        Field(description="The ID of the service provider for the airtime purchase."),
    ]

    model_config: ConfigDict = ConfigDict(
        json_schema_extra={
            "example": {
                "phone_number": "+2348012345678",
                "amount": 100.0,
                "service_id": "airtel",
            }
        }
    )


class AirtimeServiceSchema(BaseModel):
    serviceID: str
    name: str
    minimum_amount: float
    maximum_amount: float
    image: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "serviceID": "airtel",
                "name": "Airtel Nigeria",
                "minimum_amount": 100.0,
                "maximum_amount": 5000.0,
                "image": "https://example.com/airtel-logo.png",
            }
        }
    )


class AirtimeServiceListSchema(BaseModel):
    content: List[AirtimeServiceSchema]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": [
                    {
                        "serviceID": "airtel",
                        "name": "Airtel Nigeria",
                        "minimum_amount": 100.0,
                        "maximum_amount": 5000.0,
                        "image": "https://example.com/airtel-logo.png",
                    },
                    {
                        "serviceID": "mtn",
                        "name": "MTN Nigeria",
                        "minimum_amount": 100.0,
                        "maximum_amount": 5000.0,
                        "image": "https://example.com/mtn-logo.png",
                    },
                ]
            }
        }
    )
