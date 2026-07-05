from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from payments.database import get_session
from payments.services import PaymentService


def get_payment_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentService:
    """FastAPI-зависимость: сервис платежей, привязанный к сессии запроса."""
    return PaymentService(session)
