import uuid

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from payments.common.models.enums import PaymentStatus
from payments.common.models.payment import PaymentEvent
from payments.consumer import app as consumer
from payments.services.webhook import WebhookDeliveryError


class _FakeSession:
    """Async-CM заглушка SQLAlchemy-сессии: get() возвращает заданный платёж."""

    def __init__(self, payment) -> None:
        self._payment = payment
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, _model, _pid):
        return self._payment

    async def commit(self):
        self.commits += 1


def _payment(status: PaymentStatus = PaymentStatus.PENDING) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        processed_at=None,
        webhook_url='http://callback.test/hook',
        amount=None,
        currency='RUB',
        description=None,
        meta={},
        created_at=None,
    )


@pytest.fixture
def env(monkeypatch):
    """Изолирует обработчик: подменяет сессию, доставку webhook, публикацию и random."""
    state = SimpleNamespace(session=None, deliver=AsyncMock(), publish=AsyncMock())

    monkeypatch.setattr(consumer, 'AsyncSessionLocal', lambda: state.session)
    monkeypatch.setattr(consumer, 'deliver_webhook', state.deliver)
    monkeypatch.setattr(consumer.broker, 'publish', state.publish)

    # Детерминируем эмуляцию: задержка 0, успех при random() < SUCCESS_RATE.
    monkeypatch.setattr(consumer.settings, 'PROCESS_DELAY_MIN', 0.0)
    monkeypatch.setattr(consumer.settings, 'PROCESS_DELAY_MAX', 0.0)
    monkeypatch.setattr(consumer.settings, 'SUCCESS_RATE', 0.9)
    monkeypatch.setattr(consumer.random, 'random', lambda: 0.0)  # → succeeded
    return state


async def test_pending_payment_processed_and_webhook_sent(env):
    payment = _payment(PaymentStatus.PENDING)
    env.session = _FakeSession(payment)

    await consumer.process_payment(PaymentEvent(payment_id=payment.id))

    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.processed_at is not None
    assert env.session.commits == 1
    env.deliver.assert_awaited_once_with(payment)
    env.publish.assert_not_awaited()  # webhook доставлен → DLQ не задействована


async def test_failed_emulation_sets_failed_status(env, monkeypatch):
    monkeypatch.setattr(consumer.random, 'random', lambda: 0.99)  # >= SUCCESS_RATE → failed
    payment = _payment(PaymentStatus.PENDING)
    env.session = _FakeSession(payment)

    await consumer.process_payment(PaymentEvent(payment_id=payment.id))

    assert payment.status == PaymentStatus.FAILED


async def test_already_processed_skips_emulation(env):
    payment = _payment(PaymentStatus.SUCCEEDED)  # redelivery уже обработанного
    env.session = _FakeSession(payment)

    await consumer.process_payment(PaymentEvent(payment_id=payment.id))

    assert env.session.commits == 0  # повторно не обрабатываем (идемпотентность)
    env.deliver.assert_awaited_once_with(payment)  # но webhook пробуем доставить


async def test_missing_payment_is_acked_without_side_effects(env):
    env.session = _FakeSession(None)

    await consumer.process_payment(PaymentEvent(payment_id=uuid.uuid4()))

    env.deliver.assert_not_awaited()
    env.publish.assert_not_awaited()


async def test_webhook_failure_routes_to_dlq(env):
    env.deliver.side_effect = WebhookDeliveryError('boom')
    payment = _payment(PaymentStatus.PENDING)
    env.session = _FakeSession(payment)

    await consumer.process_payment(PaymentEvent(payment_id=payment.id))

    env.publish.assert_awaited_once()  # недоставленный webhook → публикация в DLQ
