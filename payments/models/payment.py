import uuid

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from payments import database
from payments.common.models.enums import Currency
from payments.common.models.enums import PaymentStatus


class Payment(database.Base):
    """ORM-модель платежа."""

    __tablename__ = 'payments'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(String(3), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    meta: Mapped[dict] = mapped_column(
        'metadata', JSONB, nullable=False, default=dict,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        String(16), nullable=False, default=PaymentStatus.PENDING, index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True,
    )
    webhook_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
