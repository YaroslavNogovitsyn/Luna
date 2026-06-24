from fastapi import FastAPI

from payments.api.router import api_router
from payments.api.router import api_tags


def create_app() -> FastAPI:
    """Создание приложения FastAPI."""
    app = _make_app()
    # Подключение корневого роутера
    app.include_router(router=api_router)

    return app


def _make_app() -> FastAPI:
    """Создание экземпляра FastAPI (ASGI) приложения."""
    return FastAPI(
        title='Payments Service',
        version='0.1.0',
        docs_url='/docs',
        redoc_url='/redocs',
        openapi_url='/openapi.json',
        openapi_tags=api_tags,
    )
