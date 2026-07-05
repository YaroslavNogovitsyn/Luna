import logging

from faststream import FastStream

from payments.broker import broker
from payments.broker import declare_topology
from payments.broker import dlx_exchange
from payments.broker import payments_exchange
from payments.broker import payments_new_queue
from payments.common.models.payment import PaymentEvent
from payments.configs import settings
from payments.database import AsyncSessionLocal
from payments.services import PaymentService
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
        service = PaymentService(session)
        payment = await service.process(event.payment_id)

        if payment is None:
            # Платёж не найден — повторять бессмысленно
            logger.warning('Платёж не найден: %s', event.payment_id)
            return

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
