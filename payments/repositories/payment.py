import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payments.models.payment import Payment


class PaymentRepository:
    """CRUD-доступ к платежам в рамках одной сессии."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, payment_id: uuid.UUID) -> Payment | None:
        """Возвращает платёж по идентификатору или None, если не найден."""
        return await self._session.get(Payment, payment_id)

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """Возвращает платёж по Idempotency-Key или None, если не найден."""
        stmt = select(Payment).where(Payment.idempotency_key == key)
        return await self._session.scalar(stmt)

    def add(self, payment: Payment) -> None:
        """Регистрирует новый платёж в сессии (INSERT на flush/commit)."""
        self._session.add(payment)
