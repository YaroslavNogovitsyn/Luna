"""
Брокер RabbitMQ (FastStream) и описание топологии.

Топология:

    payments (direct exchange)
        --[payments.new]--> payments.new (очередь)
                              x-dead-letter-exchange: payments.dlx
                              x-dead-letter-routing-key: payments.dead

    payments.dlx (direct exchange, DLX)
        --[payments.dead]--> payments.dlq (очередь, Dead Letter Queue)

Сообщение попадает в DLQ двумя путями:
  1. Явная публикация из consumer'а, когда webhook не доставлен после
     всех retry-попыток.
  2. RabbitMQ dead-lettering, если сообщение отклонено без requeue
     (например, consumer упал/выбросил необработанное исключение).
"""

from faststream.rabbit import ExchangeType
from faststream.rabbit import RabbitBroker
from faststream.rabbit import RabbitExchange
from faststream.rabbit import RabbitQueue

from payments.configs import settings


broker = RabbitBroker(settings.RABBITMQ_URL)

# --- Exchanges ---
payments_exchange = RabbitExchange(
    settings.PAYMENTS_EXCHANGE,
    type=ExchangeType.DIRECT,
    durable=True,
)

dlx_exchange = RabbitExchange(
    settings.PAYMENTS_DLX,
    type=ExchangeType.DIRECT,
    durable=True,
)

# --- Queues ---
payments_new_queue = RabbitQueue(
    settings.PAYMENTS_NEW_QUEUE,
    durable=True,
    routing_key=settings.PAYMENTS_NEW_ROUTING_KEY,
    arguments={
        'x-dead-letter-exchange': settings.PAYMENTS_DLX,
        'x-dead-letter-routing-key': settings.PAYMENTS_DEAD_ROUTING_KEY,
    },
)

dlq_queue = RabbitQueue(
    settings.PAYMENTS_DLQ,
    durable=True,
    routing_key=settings.PAYMENTS_DEAD_ROUTING_KEY,
)


async def declare_topology() -> None:
    """
    Идемпотентно объявляет exchange'и, очереди и привязки.

    Вызывается и в API (publisher), и в consumer'е, чтобы события не
    терялись, даже если consumer ещё не поднялся.
    """
    ex = await broker.declare_exchange(payments_exchange)
    dlx = await broker.declare_exchange(dlx_exchange)

    new_q = await broker.declare_queue(payments_new_queue)
    await new_q.bind(ex, routing_key=settings.PAYMENTS_NEW_ROUTING_KEY)

    dlq = await broker.declare_queue(dlq_queue)
    await dlq.bind(dlx, routing_key=settings.PAYMENTS_DEAD_ROUTING_KEY)
