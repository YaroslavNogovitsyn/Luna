from collections.abc import Sequence
from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payments.models.outbox import OutboxMessage


class OutboxRepository:
    """Доступ к событиям outbox в рамках одной сессии."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, message: OutboxMessage) -> None:
        """Регистрирует событие в сессии (пишется в одной транзакции с платежом)."""
        self._session.add(message)

    async def fetch_unpublished(self, limit: int) -> Sequence[OutboxMessage]:
        """
        Блокирует и возвращает пачку неопубликованных событий.

        Использует ``SELECT ... FOR UPDATE SKIP LOCKED`` — вызывать только внутри активной транзакции.
        """
        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.published_at.is_(None))
            .order_by(OutboxMessage.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return (await self._session.scalars(stmt)).all()

    def mark_published(self, message: OutboxMessage) -> None:
        """Помечает событие как опубликованное текущим временем (UTC)."""
        message.published_at = datetime.now(tz=UTC)
