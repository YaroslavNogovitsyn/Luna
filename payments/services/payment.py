import logging
import uuid

from datetime import UTC
from datetime import datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payments.common.models.enums import Currency
from payments.common.models.enums import PaymentStatus
from payments.configs import settings
from payments.models.outbox import OutboxMessage
from payments.models.payment import Payment
from payments.repositories import OutboxRepository
from payments.repositories import PaymentRepository
from payments.services.gateway import PaymentGateway


logger = logging.getLogger('payments.service')


class PaymentService:
    """Инкапсулирует сценарии работы с платежами."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        payments: PaymentRepository | None = None,
        outbox: OutboxRepository | None = None,
        gateway: PaymentGateway | None = None,
    ) -> None:
        self._session = session
        self._payments = payments or PaymentRepository(session)
        self._outbox = outbox or OutboxRepository(session)
        self._gateway = gateway or PaymentGateway()

    async def get(self, payment_id: uuid.UUID) -> Payment | None:
        """Возвращает платёж по идентификатору или None, если не найден."""
        return await self._payments.get(payment_id)

    async def create(
        self,
        *,
        amount: Decimal,
        currency: Currency,
        description: str | None,
        metadata: dict,
        webhook_url: str,
        idempotency_key: str,
    ) -> tuple[Payment, bool]:
        """
        Создаёт платёж и событие outbox в одной транзакции.

        Возвращает ``(payment, created)``. ``created=False``, если платёж
        с таким Idempotency-Key уже существует — тогда возвращаем
        существующий (защита от дублей).
        """
        existing = await self._payments.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing, False

        payment = Payment(
            amount=amount,
            currency=currency,
            description=description,
            meta=metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            webhook_url=webhook_url,
        )
        self._payments.add(payment)
        await self._session.flush()  # получаем payment.id

        # Outbox: событие пишется в БД в той же транзакции, что и платёж —
        # это гарантирует, что оно не потеряется, а relay опубликует его позже.
        self._outbox.add(
            OutboxMessage(
                aggregate_id=payment.id,
                routing_key=settings.PAYMENTS_NEW_ROUTING_KEY,
                payload={'payment_id': str(payment.id)},
            ),
        )

        try:
            await self._session.commit()
        except IntegrityError:
            # Гонка по уникальному idempotency_key — откатываемся и возвращаем существующий платёж.
            await self._session.rollback()
            existing = await self._payments.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing, False
            raise

        await self._session.refresh(payment)
        return payment, True

    async def process(self, payment_id: uuid.UUID) -> Payment | None:
        """
        Обрабатывает платёж через платёжный шлюз и фиксирует статус.

        Идемпотентно: эмуляция выполняется только для платежа в статусе
        ``pending``. При повторной доставке (redelivery) статус уже
        выставлен — платёж возвращается без изменений. Возвращает None,
        если платёж не найден (повторять обработку бессмысленно).
        """
        payment = await self._payments.get(payment_id)
        if payment is None:
            return None

        if payment.status != PaymentStatus.PENDING:
            logger.info(
                'Платёж уже обработан (redelivery): payment=%s status=%s',
                payment.id,
                payment.status,
            )
            return payment

        succeeded = await self._gateway.charge()
        payment.status = PaymentStatus.SUCCEEDED if succeeded else PaymentStatus.FAILED
        payment.processed_at = datetime.now(tz=UTC)
        await self._session.commit()

        logger.info(
            'Платёж обработан: payment=%s status=%s',
            payment.id,
            payment.status,
        )
        return payment
