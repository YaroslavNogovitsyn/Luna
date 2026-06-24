from datetime import UTC
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse


# Создание экземпляра роутера
router = APIRouter()


@router.get('/health', name='health-check')
def health_check() -> JSONResponse:
    """Вью для отдачи статуса сервиса."""
    # Получение и сохранение текущего времени
    server_dt = datetime.now()
    server_dt_utc = datetime.now(tz=UTC)

    # Формирование словаря для ответа
    response = {
        # Общий статус сервиса
        'status': 'OK',
        # Информация о сервисе
        'service': {
            'name': 'Payments Service',
            'version': '0.1.0',
        },
        # Информация о сервере
        'server': {
            'dt': int(server_dt.timestamp()),
            'dt_utc': int(server_dt_utc.timestamp()),
            'dtf': server_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'dtf_utc': server_dt_utc.strftime('%Y-%m-%d %H:%M:%S'),
        },
    }

    # Отдача ответа в формате JSON
    return JSONResponse(content=response)
