import pytest

from fastapi import HTTPException

from payments.common.utils import security


def test_valid_key_passes(monkeypatch):
    monkeypatch.setattr(security.settings, 'API_KEY', 'secret')

    assert security.require_api_key(x_api_key='secret') is None


def test_invalid_key_rejected(monkeypatch):
    monkeypatch.setattr(security.settings, 'API_KEY', 'secret')

    with pytest.raises(HTTPException) as exc_info:
        security.require_api_key(x_api_key='wrong')

    assert exc_info.value.status_code == 401


def test_empty_key_rejected(monkeypatch):
    monkeypatch.setattr(security.settings, 'API_KEY', 'secret')

    with pytest.raises(HTTPException) as exc_info:
        security.require_api_key(x_api_key='')

    assert exc_info.value.status_code == 401
