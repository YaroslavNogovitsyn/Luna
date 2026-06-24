import uuid

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from payments import database


class OutboxMessage(database.Base):
    """Outbox: события сохраняются в одной транзакции с платежом, затем relay-процесс публикует их в брокер."""

    __tablename__ = 'outbox'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    aggregate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    routing_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        Index('ix_outbox_unpublished', 'published_at', 'created_at'),
    )
