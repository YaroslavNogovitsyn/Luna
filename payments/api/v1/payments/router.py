__all__ = [
    'router',
]

import uuid

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import Response
from fastapi import status

from payments.api.v1.payments.dependencies import get_payment_service
from payments.api.v1.payments.models.request import PaymentCreate
from payments.api.v1.payments.models.response import PaymentCreatedResponse
from payments.api.v1.payments.models.response import PaymentRead
from payments.common.utils.security import require_api_key
from payments.services import PaymentService


router = APIRouter(
    prefix='/payments',
    dependencies=[Depends(require_api_key)],
)


@router.get(
    '/{payment_id}',
    status_code=status.HTTP_200_OK,
    response_model_by_alias=True,
)
async def get_payment(
    payment_id: uuid.UUID,
    *,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentRead:
    payment = await service.get(payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Payment not found',
        )
    return PaymentRead.model_validate(payment)


@router.post(
    '',
    status_code=status.HTTP_202_ACCEPTED,
    response_model_by_alias=True,
)
async def create_payment(
    *,
    data: PaymentCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(alias='Idempotency-Key')],
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentCreatedResponse:
    payment, created = await service.create(
        amount=data.amount,
        currency=data.currency,
        description=data.description,
        metadata=data.metadata,
        webhook_url=data.webhook_url,
        idempotency_key=idempotency_key,
    )
    if not created:
        # Повторный запрос с тем же ключом — возвращаем существующий платёж.
        response.status_code = status.HTTP_200_OK

    return PaymentCreatedResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )
