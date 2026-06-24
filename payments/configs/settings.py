from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parents[2] / '.env'


class Settings(BaseSettings):
    """Конфигурация приложения через pydantic-settings."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # --- Аутентификация ---
    API_KEY: str = 'supersecret-api-key'

    # --- База данных (асинхронный драйвер) ---
    DATABASE_URL: str = (
        'postgresql+asyncpg://payments:payments@postgres:5432/payments'
    )

    PAYMENTS_NEW_ROUTING_KEY: str = 'payments.new'


settings = Settings()
