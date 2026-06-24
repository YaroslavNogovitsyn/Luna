from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from payments.configs import settings


def require_api_key(x_api_key: str = Header(..., alias='X-API-Key')) -> None:
    """Аутентификация по статическому API-ключу (заголовок X-API-Key)."""
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or missing API key',
        )
