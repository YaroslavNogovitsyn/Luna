import asyncio
import contextlib
import logging

from collections.abc import AsyncIterator

from fastapi import FastAPI

from payments.broker import broker
from payments.broker import declare_topology
from payments.outbox.relay import run_outbox_relay


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger('payments.api')


@contextlib.asynccontextmanager
async def initialize(_: FastAPI) -> AsyncIterator[None]:
    """Lifespan-функция всего приложения."""
    # Загрузка справочников из Redis в память приложения
    await broker.connect()
    await declare_topology()

    stop_event = asyncio.Event()
    relay_task = asyncio.create_task(run_outbox_relay(stop_event))
    logger.info('API запущен')

    try:
        yield
    finally:
        stop_event.set()
        relay_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay_task
        await broker.close()
        logger.info('API остановлен')
