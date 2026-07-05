import asyncio
import random

from payments.configs import settings


class PaymentGateway:
    """Имитирует обращение к платёжному шлюзу: задержка + вероятностный исход."""

    async def charge(self) -> bool:
        """Эмулирует обработку платежа."""
        delay = random.uniform(settings.PROCESS_DELAY_MIN, settings.PROCESS_DELAY_MAX)  # noqa: S311 — эмуляция, не криптография
        await asyncio.sleep(delay)
        return random.random() < settings.SUCCESS_RATE  # noqa: S311 — эмуляция, не криптография
