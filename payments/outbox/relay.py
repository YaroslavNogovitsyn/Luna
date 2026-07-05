"""
Outbox relay: фоновый процесс публикации событий из таблицы outbox.

Гарантирует at-least-once доставку события в брокер: событие пишется в
outbox в одной транзакции с платежом, а relay опрашивает таблицу и
публикует неотправленные сообщения, помечая их published_at.

Используется SELECT ... FOR UPDATE SKIP LOCKED, чтобы несколько
экземпляров API могли работать параллельно без дублей.
"""

import asyncio
import contextlib
import logging

from payments.broker import broker
from payments.broker import payments_exchange
from payments.configs import settings
from payments.database import AsyncSessionLocal
from payments.repositories import OutboxRepository


logger = logging.getLogger('payments.outbox')


async def _publish_batch() -> int:
    async with AsyncSessionLocal() as session, session.begin():
        repo = OutboxRepository(session)
        messages = await repo.fetch_unpublished(settings.OUTBOX_BATCH_SIZE)

        for message in messages:
            await broker.publish(
                message.payload,
                exchange=payments_exchange,
                routing_key=message.routing_key,
            )
            repo.mark_published(message)

        return len(messages)


async def run_outbox_relay(stop_event: asyncio.Event) -> None:
    """Бесконечный цикл публикации, останавливается по stop_event."""
    logger.info('Outbox relay запущен')
    while not stop_event.is_set():
        try:
            count = await _publish_batch()
            if count:
                logger.info('Outbox: опубликовано сообщений: %s', count)
        except Exception:
            logger.exception('Ошибка в outbox relay, повтор через интервал')

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                stop_event.wait(), timeout=settings.OUTBOX_POLL_INTERVAL,
            )

    logger.info('Outbox relay остановлен')
