from decimal import Decimal

from pydantic import BaseModel
from pydantic import Field

from payments.common.models.enums import Currency


class PaymentCreate(BaseModel):
    """Тело запроса на создание платежа."""

    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str | None = Field(default=None, max_length=512)
    metadata: dict = Field(default_factory=dict)
    webhook_url: str = Field(min_length=1, max_length=2048)
