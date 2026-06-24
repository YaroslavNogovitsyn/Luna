import asyncio
import logging

import httpx

from payments.configs import settings
from payments.models.payment import Payment


logger = logging.getLogger('payments.webhook')


class WebhookDeliveryError(Exception):
    """Webhook не удалось доставить после всех попыток."""


def _build_payload(payment: Payment) -> dict:
    return {
        'payment_id': str(payment.id),
        'status': payment.status,
        'amount': str(payment.amount),
        'currency': payment.currency,
        'description': payment.description,
        'metadata': payment.meta,
        'created_at': payment.created_at.isoformat(),
        'processed_at': (
            payment.processed_at.isoformat() if payment.processed_at else None
        ),
    }


async def deliver_webhook(payment: Payment) -> None:
    """
    Отправляет webhook с экспоненциальным backoff.

    Делает до ``WEBHOOK_MAX_ATTEMPTS`` попыток. Задержка перед попыткой
    n (начиная с 1) — ``backoff_base * 2**(n-1)`` секунд.
    Если все попытки неуспешны — бросает WebhookDeliveryError.
    """
    payload = _build_payload(payment)
    max_attempts = settings.WEBHOOK_MAX_ATTEMPTS
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(payment.webhook_url, json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    'Ошибка доставки webhook: payment=%s attempt=%s/%s error=%s',
                    payment.id,
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt < max_attempts:
                    delay = settings.WEBHOOK_BACKOFF_BASE * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
            else:
                logger.info(
                    'Webhook доставлен: payment=%s attempt=%s status=%s',
                    payment.id,
                    attempt,
                    response.status_code,
                )
                return

    raise WebhookDeliveryError(
        f'Не удалось доставить webhook для платежа {payment.id} после {max_attempts} попыток: {last_error}',
    )
