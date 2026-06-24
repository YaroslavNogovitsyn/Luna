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

    # --- RabbitMQ ---
    RABBITMQ_URL: str = 'amqp://guest:guest@rabbitmq:5672/'

    # --- Топология RabbitMQ ---
    PAYMENTS_EXCHANGE: str = 'payments'
    PAYMENTS_DLX: str = 'payments.dlx'
    PAYMENTS_NEW_QUEUE: str = 'payments.new'
    PAYMENTS_DLQ: str = 'payments.dlq'
    PAYMENTS_NEW_ROUTING_KEY: str = 'payments.new'
    PAYMENTS_DEAD_ROUTING_KEY: str = 'payments.dead'

    # --- Outbox relay ---
    OUTBOX_POLL_INTERVAL: float = 1.0
    OUTBOX_BATCH_SIZE: int = 100

    # --- Эмуляция обработки платежа ---
    PROCESS_DELAY_MIN: float = 2.0
    PROCESS_DELAY_MAX: float = 5.0
    SUCCESS_RATE: float = 0.9

    # --- Доставка webhook / retry ---
    WEBHOOK_MAX_ATTEMPTS: int = 3
    WEBHOOK_BACKOFF_BASE: float = 1.0  # секунды: base * 2**(attempt-1)
    WEBHOOK_TIMEOUT: float = 10.0


settings = Settings()
