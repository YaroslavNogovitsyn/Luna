import uuid

from datetime import UTC
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from pydantic import ValidationError

from payments.api.v1.payments.models.request import PaymentCreate
from payments.api.v1.payments.models.response import PaymentCreatedResponse
from payments.api.v1.payments.models.response import PaymentRead
from payments.common.models.enums import Currency
from payments.common.models.enums import PaymentStatus


def test_payment_create_valid_defaults():
    model = PaymentCreate(amount=Decimal('10.00'), currency='RUB', webhook_url='http://x')

    assert model.currency is Currency.RUB
    assert model.metadata == {}
    assert model.description is None


@pytest.mark.parametrize('amount', ['0', '-1', '-0.01'])
def test_payment_create_rejects_non_positive_amount(amount):
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal(amount), currency='RUB', webhook_url='http://x')


def test_payment_create_rejects_unknown_currency():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal(1), currency='GBP', webhook_url='http://x')


def test_payment_create_rejects_empty_webhook_url():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal(1), currency='RUB', webhook_url='')


def _orm_like():
    return SimpleNamespace(
        id=uuid.uuid4(),
        amount=Decimal('199.90'),
        currency=Currency.RUB,
        description='Подписка Pro',
        meta={'order_id': 42},
        status=PaymentStatus.SUCCEEDED,
        idempotency_key='key-1',
        webhook_url='http://x',
        created_at=datetime(2026, 6, 22, 10, 0, 3, tzinfo=UTC),
        processed_at=datetime(2026, 6, 22, 10, 0, 7, tzinfo=UTC),
    )


def test_payment_read_validates_from_attributes_and_serializes_snake_case():
    model = PaymentRead.model_validate(_orm_like())  # требует from_attributes=True

    dumped = model.model_dump(by_alias=True, mode='json')

    # контракт snake_case (не camelCase)
    assert dumped['idempotency_key'] == 'key-1'
    assert dumped['webhook_url'] == 'http://x'
    # поле meta наружу отдаётся как metadata
    assert dumped['metadata'] == {'order_id': 42}
    assert 'meta' not in dumped
    # сумма — строкой, точность сохранена
    assert dumped['amount'] == '199.90'
    # даты с секундами и суффиксом Z для UTC
    assert dumped['created_at'] == '2026-06-22T10:00:03Z'
    assert dumped['processed_at'] == '2026-06-22T10:00:07Z'


def test_payment_created_response_serializes_snake_case():
    pid = uuid.uuid4()
    model = PaymentCreatedResponse(
        payment_id=pid,
        status=PaymentStatus.PENDING,
        created_at=datetime(2026, 6, 22, 10, 0, 0, tzinfo=UTC),
    )

    dumped = model.model_dump(by_alias=True, mode='json')

    assert dumped['payment_id'] == str(pid)
    assert dumped['status'] == 'pending'
    assert dumped['created_at'] == '2026-06-22T10:00:00Z'
