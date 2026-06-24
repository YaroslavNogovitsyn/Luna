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

from datetime import UTC
from datetime import datetime

from sqlalchemy import select

from payments.broker import broker
from payments.broker import payments_exchange
from payments.configs import settings
from payments.database import AsyncSessionLocal
from payments.models.outbox import OutboxMessage


logger = logging.getLogger('payments.outbox')


async def _publish_batch() -> int:
    async with AsyncSessionLocal() as session, session.begin():
        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.published_at.is_(None))
            .order_by(OutboxMessage.created_at)
            .limit(settings.OUTBOX_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        messages = (await session.scalars(stmt)).all()

        for message in messages:
            await broker.publish(
                message.payload,
                exchange=payments_exchange,
                routing_key=message.routing_key,
            )
            message.published_at = datetime.now(tz=UTC)

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
