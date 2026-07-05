import uuid

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from payments.common.models.payment import PaymentEvent
from payments.consumer import app as consumer
from payments.services.webhook import WebhookDeliveryError


class _FakeSessionCM:
    """Async-CM заглушка сессии — тело обработки её не использует напрямую."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def env(monkeypatch):
    """
    Изолирует тонкий обработчик: подменяет сервис, доставку webhook и публикацию.

    Обработка платежа целиком делегирована PaymentService (тестируется
    отдельно в test_payment_service.py) — здесь проверяется только
    оркестрация: что и в каком порядке дёргает consumer.
    """
    state = SimpleNamespace(
        service=SimpleNamespace(process=AsyncMock()),
        deliver=AsyncMock(),
        publish=AsyncMock(),
    )

    monkeypatch.setattr(consumer, 'AsyncSessionLocal', _FakeSessionCM)
    monkeypatch.setattr(consumer, 'PaymentService', lambda _session: state.service)
    monkeypatch.setattr(consumer, 'deliver_webhook', state.deliver)
    monkeypatch.setattr(consumer.broker, 'publish', state.publish)
    return state


def _payment() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), webhook_url='http://callback.test/hook')


async def test_processed_payment_triggers_webhook(env):
    payment = _payment()
    env.service.process.return_value = payment

    await consumer.process_payment(PaymentEvent(payment_id=payment.id))

    env.service.process.assert_awaited_once_with(payment.id)
    env.deliver.assert_awaited_once_with(payment)
    env.publish.assert_not_awaited()  # webhook доставлен → DLQ не задействована


async def test_missing_payment_is_acked_without_side_effects(env):
    env.service.process.return_value = None  # платёж не найден

    await consumer.process_payment(PaymentEvent(payment_id=uuid.uuid4()))

    env.deliver.assert_not_awaited()
    env.publish.assert_not_awaited()


async def test_webhook_failure_routes_to_dlq(env):
    payment = _payment()
    env.service.process.return_value = payment
    env.deliver.side_effect = WebhookDeliveryError('boom')

    await consumer.process_payment(PaymentEvent(payment_id=payment.id))

    env.publish.assert_awaited_once()  # недоставленный webhook → публикация в DLQ
