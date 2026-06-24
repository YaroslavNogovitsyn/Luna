from fastapi import APIRouter

from payments.api import health
from payments.api.v1.router import router as v1_router


# Теги для документации API
api_tags = [
    {
        'name': 'Сервисное API',
        'description': 'Общая группа сервисного API',
    },
]

# Создание экземпляра базового роутера, в который будут регистрироваться все основные ресурсы (URL-ы)
api_router = APIRouter(prefix='/api')

# Подключение вью для отдачи настроек, статуса сервиса, статуса внешних сервисов и др.
api_router.include_router(router=health.router, tags=['Сервисное API'])

# Подключение разных версий API
api_router.include_router(router=v1_router)
