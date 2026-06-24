"""
Consumer: единственный обработчик очереди payments.new.

Обработчик делает всё:
  1. Получает событие из очереди payments.new.
  2. Эмулирует обработку платежа (2-5 сек, 90% успех / 10% ошибка).
  3. Обновляет статус платежа в БД.
  4. Отправляет webhook-уведомление с retry и экспоненциальной задержкой.
  5. Если webhook не доставлен после всех попыток — публикует сообщение
     в Dead Letter Queue.

Идемпотентность: эмуляция выполняется только если платёж в статусе
pending. При повторной доставке (redelivery) статус уже выставлен —
тогда обработчик лишь пытается доставить webhook повторно.
"""

import asyncio
import logging
import random

from datetime import UTC
from datetime import datetime

from faststream import FastStream

from payments.broker import broker
from payments.broker import declare_topology
from payments.broker import dlx_exchange
from payments.broker import payments_exchange
from payments.broker import payments_new_queue
from payments.common.models.enums import PaymentStatus
from payments.common.models.payment import PaymentEvent
from payments.configs import settings
from payments.database import AsyncSessionLocal
from payments.models.payment import Payment
from payments.services.webhook import WebhookDeliveryError
from payments.services.webhook import deliver_webhook


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger('payments.consumer')

payments = FastStream(broker)


@payments.after_startup
async def on_startup() -> None:
    """Объявляет топологию брокера при старте consumer'а."""
    await declare_topology()
    logger.info('Consumer запущен')


async def _emulate_processing(payment: Payment) -> None:
    """Эмулирует обработку платежа через внешний шлюз."""
    delay = random.uniform(settings.PROCESS_DELAY_MIN, settings.PROCESS_DELAY_MAX)  # noqa: S311 — эмуляция, не криптография
    await asyncio.sleep(delay)

    succeeded = random.random() < settings.SUCCESS_RATE  # noqa: S311 — эмуляция, не криптография
    payment.status = PaymentStatus.SUCCEEDED if succeeded else PaymentStatus.FAILED
    payment.processed_at = datetime.now(tz=UTC)
    logger.info(
        'Платёж обработан: payment=%s status=%s (delay=%.2fs)',
        payment.id,
        payment.status,
        delay,
    )


async def _send_to_dlq(event: PaymentEvent, /, *, reason: str, attempts: int) -> None:
    """Явно публикует сообщение в DLQ."""
    await broker.publish(
        event,
        exchange=dlx_exchange,
        routing_key=settings.PAYMENTS_DEAD_ROUTING_KEY,
        headers={'x-death-reason': reason, 'x-attempts': str(attempts)},
    )
    logger.error(
        'Сообщение отправлено в DLQ: payment=%s reason=%s',
        event.payment_id,
        reason,
    )


@broker.subscriber(payments_new_queue, payments_exchange, retry=False)
async def process_payment(event: PaymentEvent) -> None:
    """Обрабатывает платёж из очереди и доставляет webhook (с DLQ при отказе)."""
    async with AsyncSessionLocal() as session:
        payment = await session.get(Payment, event.payment_id)

        if payment is None:
            # Платёж не найден — повторять бессмысленно
            logger.warning('Платёж не найден: %s', event.payment_id)
            return

        # --- Обработка (идемпотентно) ---
        if payment.status == PaymentStatus.PENDING:
            await _emulate_processing(payment)
            await session.commit()
        else:
            logger.info(
                'Платёж уже обработан (redelivery): payment=%s status=%s',
                payment.id,
                payment.status,
            )

        # --- Доставка webhook с retry/backoff ---
        try:
            await deliver_webhook(payment)
        except WebhookDeliveryError:
            # Все попытки исчерпаны → в DLQ. Сообщение из основной очереди подтверждаем — повторно отправлять не нужно
            await _send_to_dlq(
                event,
                reason='webhook-delivery-failed',
                attempts=settings.WEBHOOK_MAX_ATTEMPTS,
            )
            logger.exception('Webhook окончательно не доставлен')
