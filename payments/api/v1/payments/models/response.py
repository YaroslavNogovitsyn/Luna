import uuid

from datetime import datetime
from decimal import Decimal

from pydantic import Field
from pydantic import field_serializer

from payments.common.models.enums import Currency
from payments.common.models.enums import PaymentStatus
from payments.common.models.response import BaseResponseModel


class PaymentRead(BaseResponseModel):
    """Детальная информация о платеже."""

    id: uuid.UUID
    amount: Decimal
    currency: Currency
    description: str | None
    meta: dict = Field(serialization_alias='metadata')
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None

    @field_serializer('amount')
    def serialize_amount(self, value: Decimal) -> str:
        """Сериализует сумму в строку, сохраняя точность Decimal."""
        return str(value)


class PaymentCreatedResponse(BaseResponseModel):
    """Ответ 202 Accepted на создание платежа."""

    payment_id: uuid.UUID
    status: PaymentStatus
    created_at: datetime
