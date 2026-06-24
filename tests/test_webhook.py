import uuid

from datetime import UTC
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from payments.common.models.enums import PaymentStatus
from payments.services import webhook
from payments.services.webhook import WebhookDeliveryError
from payments.services.webhook import deliver_webhook


def make_payment(url: str = 'http://callback.test/hook') -> SimpleNamespace:
    """Лёгкий объект-заглушка платежа (вместо ORM) с нужными webhook атрибутами."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=PaymentStatus.SUCCEEDED,
        amount=Decimal('199.90'),
        currency='RUB',
        description='Подписка Pro',
        meta={'order_id': 42},
        webhook_url=url,
        created_at=datetime(2026, 6, 22, 10, 0, 0, tzinfo=UTC),
        processed_at=datetime(2026, 6, 22, 10, 0, 3, tzinfo=UTC),
    )


class _FakeResponse:
    def __init__(self, status_code: int = 200, error: Exception | None = None) -> None:
        self.status_code = status_code
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error


def _ok() -> _FakeResponse:
    return _FakeResponse(200)


@pytest.fixture
def hook(monkeypatch):
    """
    Подменяет httpx.AsyncClient и asyncio.sleep в модуле webhook.

    state.behaviors — очередь ответов/исключений для последовательных post().
    state.calls — фактические вызовы post().
    state.delays — задержки, переданные в asyncio.sleep (для проверки backoff).
    """
    state = SimpleNamespace(behaviors=[], calls=[], delays=[])

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            state.calls.append((url, json))
            behavior = state.behaviors.pop(0)
            if isinstance(behavior, Exception):
                raise behavior
            return behavior

    async def fake_sleep(delay):
        state.delays.append(delay)

    monkeypatch.setattr(webhook.httpx, 'AsyncClient', FakeClient)
    monkeypatch.setattr(webhook.asyncio, 'sleep', fake_sleep)
    monkeypatch.setattr(webhook.settings, 'WEBHOOK_MAX_ATTEMPTS', 3)
    monkeypatch.setattr(webhook.settings, 'WEBHOOK_BACKOFF_BASE', 1.0)
    monkeypatch.setattr(webhook.settings, 'WEBHOOK_TIMEOUT', 5.0)
    return state


async def test_delivers_on_first_attempt(hook):
    hook.behaviors = [_ok()]

    await deliver_webhook(make_payment())

    assert len(hook.calls) == 1
    assert hook.delays == []  # успех с первой попытки — без задержек


async def test_retries_then_succeeds(hook):
    hook.behaviors = [httpx.ConnectError('down'), _ok()]

    await deliver_webhook(make_payment())

    assert len(hook.calls) == 2
    assert hook.delays == [1.0]  # base * 2**0 перед второй попыткой


async def test_exhausts_attempts_and_raises(hook):
    hook.behaviors = [httpx.ConnectError('down')] * 3

    with pytest.raises(WebhookDeliveryError):
        await deliver_webhook(make_payment())

    assert len(hook.calls) == 3  # ровно WEBHOOK_MAX_ATTEMPTS
    assert hook.delays == [1.0, 2.0]  # экспоненциальный backoff между попытками


async def test_http_5xx_triggers_retry(hook):
    request = httpx.Request('POST', 'http://callback.test/hook')
    error = httpx.HTTPStatusError('500', request=request, response=httpx.Response(500, request=request))
    hook.behaviors = [_FakeResponse(500, error=error), _ok()]

    await deliver_webhook(make_payment())

    assert len(hook.calls) == 2  # 5xx считается ошибкой → повтор


def test_build_payload_shape():
    payment = make_payment()

    payload = webhook._build_payload(payment)

    assert payload['payment_id'] == str(payment.id)
    assert payload['amount'] == '199.90'  # сумма строкой, точность сохранена
    assert payload['status'] == PaymentStatus.SUCCEEDED
    assert payload['metadata'] == {'order_id': 42}
    assert payload['processed_at'] == payment.processed_at.isoformat()
