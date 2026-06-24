import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payments.api.v1.payments.models.request import PaymentCreate
from payments.common.models.enums import PaymentStatus
from payments.configs import settings
from payments.models.outbox import OutboxMessage
from payments.models.payment import Payment


async def get_payment(session: AsyncSession, /, *, payment_id: uuid.UUID) -> Payment | None:
    """Возвращает платёж по идентификатору или None, если он не найден."""
    return await session.get(Payment, payment_id)


async def get_by_idempotency_key(session: AsyncSession, /, *, key: str) -> Payment | None:
    """Возвращает платёж по Idempotency-Key или None, если он не найден."""
    stmt = select(Payment).where(Payment.idempotency_key == key)
    return await session.scalar(stmt)


async def create_payment(
    session: AsyncSession,
    /,
    *,
    data: PaymentCreate,
    idempotency_key: str,
) -> tuple[Payment, bool]:
    """
    Создаёт платёж и событие outbox в одной транзакции.

    Возвращает (payment, created). created=False, если платёж с таким
    Idempotency-Key уже существует — тогда возвращаем существующий
    (защита от дублей).
    """
    existing = await get_by_idempotency_key(session, key=idempotency_key)
    if existing is not None:
        return existing, False

    payment = Payment(
        amount=data.amount,
        currency=data.currency,
        description=data.description,
        meta=data.metadata,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        webhook_url=data.webhook_url,
    )
    session.add(payment)
    await session.flush()  # получаем payment.id

    # Outbox: публикация события гарантируется тем, что запись попадает в БД в той же транзакции, что и сам платёж
    outbox = OutboxMessage(
        aggregate_id=payment.id,
        routing_key=settings.PAYMENTS_NEW_ROUTING_KEY,
        payload={'payment_id': str(payment.id)},
    )
    session.add(outbox)

    try:
        await session.commit()
    except IntegrityError:
        # Гонка по уникальному idempotency_key — откатываемся и возвращаем уже существующий платёж
        await session.rollback()
        existing = await get_by_idempotency_key(session, key=idempotency_key)
        if existing is not None:
            return existing, False
        raise

    await session.refresh(payment)
    return payment, True
