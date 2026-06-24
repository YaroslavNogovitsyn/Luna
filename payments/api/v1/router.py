from fastapi import APIRouter

from payments.api.v1.payments import router as payments


# Создание экземпляра роутера API v1
router = APIRouter(prefix='/v1')

router.include_router(router=payments)
