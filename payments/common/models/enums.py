from enum import StrEnum


class Currency(StrEnum):
    """Валюта."""

    RUB = 'RUB'
    USD = 'USD'
    EUR = 'EUR'


class PaymentStatus(StrEnum):
    """Статус оплаты."""

    PENDING = 'pending'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
