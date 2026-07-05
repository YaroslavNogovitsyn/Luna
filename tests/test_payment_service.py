import uuid

from decimal import Decimal
from types import SimpleNamespace

import pytest

from payments.common.models.enums import Currency
from payments.common.models.enums import PaymentStatus
from payments.models.payment import Payment
from payments.services import PaymentService


class FakeSession:
    """Заглушка AsyncSession: считает commit/rollback/refresh, эмулирует flush."""

    def __init__(self) -> None:
        self.new: list = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.refreshes = 0

    async def flush(self) -> None:
        self.flushes += 1
        for obj in self.new:
            if isinstance(obj, Payment) and obj.id is None:
                obj.id = uuid.uuid4()  # эмулируем присвоение PK базой

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def refresh(self, _obj) -> None:
        self.refreshes += 1


class FakePaymentRepository:
    """Заглушка PaymentRepository поверх словарей в памяти."""

    def __init__(self, session: FakeSession, existing: list | None = None) -> None:
        self._session = session
        self._by_id: dict = {}
        self._by_key: dict = {}
        for payment in existing or []:
            self._by_id[payment.id] = payment
            self._by_key[payment.idempotency_key] = payment

    async def get(self, payment_id):
        return self._by_id.get(payment_id)

    async def get_by_idempotency_key(self, key):
        return self._by_key.get(key)

    def add(self, payment) -> None:
        self._session.new.append(payment)


class FakeOutboxRepository:
    """Заглушка OutboxRepository: копит добавленные события."""

    def __init__(self, session: FakeSession) -> None:
        self._session = session
        self.added: list = []

    def add(self, message) -> None:
        self.added.append(message)
        self._session.new.append(message)


class FakeGateway:
    """Детерминированный платёжный шлюз: всегда возвращает заданный исход."""

    def __init__(self, *, result: bool) -> None:
        self._result = result
        self.calls = 0

    async def charge(self) -> bool:
        self.calls += 1
        return self._result


def _build_service(session, existing=None, *, gateway_result=True):
    payments = FakePaymentRepository(session, existing=existing)
    outbox = FakeOutboxRepository(session)
    gateway = FakeGateway(result=gateway_result)
    service = PaymentService(session, payments=payments, outbox=outbox, gateway=gateway)
    return service, payments, outbox, gateway


def _existing_payment(status: PaymentStatus = PaymentStatus.PENDING) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        idempotency_key='key-1',
        status=status,
        processed_at=None,
    )


async def test_create_persists_payment_and_outbox_event():
    session = FakeSession()
    service, _payments, outbox, _gateway = _build_service(session)

    payment, created = await service.create(
        amount=Decimal('199.90'),
        currency=Currency.RUB,
        description='Подписка Pro',
        metadata={'order_id': 42},
        webhook_url='http://callback.test/hook',
        idempotency_key='key-1',
    )

    assert created is True
    assert payment.status == PaymentStatus.PENDING
    assert payment.id is not None  # присвоен на flush
    assert session.commits == 1
    assert len(outbox.added) == 1  # событие в outbox в той же транзакции
    assert outbox.added[0].payload == {'payment_id': str(payment.id)}


async def test_create_is_idempotent_for_known_key():
    session = FakeSession()
    existing = _existing_payment()
    service, _payments, outbox, _gateway = _build_service(session, existing=[existing])

    payment, created = await service.create(
        amount=Decimal('10.00'),
        currency=Currency.USD,
        description=None,
        metadata={},
        webhook_url='http://callback.test/hook',
        idempotency_key='key-1',
    )

    assert created is False
    assert payment is existing  # вернулся существующий платёж
    assert session.commits == 0  # ничего не пишем повторно
    assert outbox.added == []


@pytest.mark.parametrize(
    ('gateway_result', 'expected'),
    [(True, PaymentStatus.SUCCEEDED), (False, PaymentStatus.FAILED)],
)
async def test_process_sets_status_from_gateway(gateway_result, expected):
    session = FakeSession()
    payment = _existing_payment(PaymentStatus.PENDING)
    service, *_ = _build_service(session, existing=[payment], gateway_result=gateway_result)

    result = await service.process(payment.id)

    assert result is payment
    assert payment.status == expected
    assert payment.processed_at is not None
    assert session.commits == 1


async def test_process_skips_already_processed_payment():
    session = FakeSession()
    payment = _existing_payment(PaymentStatus.SUCCEEDED)  # redelivery
    service, _payments, _outbox, gateway = _build_service(session, existing=[payment])

    result = await service.process(payment.id)

    assert result is payment
    assert gateway.calls == 0  # шлюз не дёргаем (идемпотентность)
    assert session.commits == 0


async def test_process_returns_none_for_missing_payment():
    session = FakeSession()
    service, _payments, _outbox, gateway = _build_service(session)

    result = await service.process(uuid.uuid4())

    assert result is None
    assert gateway.calls == 0
    assert session.commits == 0
