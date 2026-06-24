import uuid

from pydantic import BaseModel


class PaymentEvent(BaseModel):
    """Событие, публикуемое в очередь payments.new."""

    payment_id: uuid.UUID
