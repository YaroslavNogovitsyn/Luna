from datetime import UTC
from datetime import datetime

from payments.common.utils.encoder import encode_datetime


def test_naive_datetime_has_no_z_suffix():
    assert encode_datetime(datetime(2026, 6, 22, 10, 0, 3)) == '2026-06-22T10:00:03'


def test_utc_datetime_has_z_suffix():
    assert encode_datetime(datetime(2026, 6, 22, 10, 0, 3, tzinfo=UTC)) == '2026-06-22T10:00:03Z'


def test_seconds_are_preserved():
    # Регрессия: ранее секунды принудительно обнулялись (`:00`).
    assert encode_datetime(datetime(2026, 6, 22, 10, 0, 59, tzinfo=UTC)) == '2026-06-22T10:00:59Z'
