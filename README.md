# Асинхронный сервис процессинга платежей

Тестовое задание (МКК «Луна»). Микросервис для асинхронной обработки
платежей: принимает запрос на оплату, обрабатывает его через эмуляцию
платёжного шлюза и уведомляет клиента о результате через webhook.

## Стек

- **FastAPI** + **Pydantic v2** — HTTP API
- **SQLAlchemy 2.0** (async) + **asyncpg** + **PostgreSQL** — хранилище
- **Alembic** — миграции
- **RabbitMQ** + **FastStream** — брокер сообщений
- **Poetry** — управление зависимостями
- **Docker** + **docker-compose** — окружение

## Архитектура

```
            POST /api/v1/payments
                   │
                   ▼
        ┌──────────────────────┐        одна транзакция
        │        API           │   ┌─────────────────────────┐
        │  (FastAPI)           │──▶│ payments + outbox (БД)   │
        │  + Outbox relay      │   └─────────────────────────┘
        └──────────┬───────────┘
                   │ relay публикует события из outbox
                   ▼
        ┌──────────────────────┐
        │  exchange: payments  │
        │   rk: payments.new   │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │ queue: payments.new  │  x-dead-letter-exchange: payments.dlx
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │      Consumer        │  эмуляция (2-5с, 90/10) → статус в БД
        │                      │  → webhook (3 попытки, exp backoff)
        └──────────┬───────────┘
                   │ если webhook не доставлен
                   ▼
        ┌──────────────────────────────────────────────┐
        │  exchange: payments.dlx (rk: payments.dead)    │
        │            ▼                                   │
        │  queue: payments.dlq  (Dead Letter Queue)      │
        └──────────────────────────────────────────────┘
```

### Слои приложения

Логика разделена по ответственности, чтобы её было легко поддерживать и
покрывать тестами:

- **Транспорт** — HTTP (`payments/api/`) и брокер (`payments/consumer/`,
  `payments/outbox/`). Тонкий слой: разбор запроса/события и вызов сервиса.
- **Сервисы** (`payments/services/`) — бизнес-логика. `PaymentService`
  реализует сценарии создания (идемпотентность + outbox в одной
  транзакции), получения и обработки платежа и переиспользуется и в API, и
  в consumer'е. `PaymentGateway` — эмуляция платёжного шлюза, `webhook` —
  доставка уведомлений с retry.
- **Репозитории** (`payments/repositories/`) — единственный слой,
  работающий с БД. `PaymentRepository` и `OutboxRepository` инкапсулируют
  все SQL-запросы; выше по стеку про SQLAlchemy никто не знает.
- **Модели** — ORM (`payments/models/`) и Pydantic-схемы
  (`payments/api/.../models/`, `payments/common/models/`).

### Реализованные требования

1. **Модели и миграции** — таблицы `payments` и `outbox`
   ([payments/models/](payments/models/), [payments/migrations/versions/0001_initial.py](payments/migrations/versions/0001_initial.py)).
2. **API эндпоинты** — создание (202) и получение платежа
   ([payments/api/v1/payments/router.py](payments/api/v1/payments/router.py)).
3. **Consumer** — один обработчик, делающий всё
   ([payments/consumer/app.py](payments/consumer/app.py)).
4. **Outbox pattern** — событие пишется в `outbox` в одной транзакции с
   платежом; фоновый relay публикует его в RabbitMQ
   (`SELECT ... FOR UPDATE SKIP LOCKED`) — [payments/outbox/relay.py](payments/outbox/relay.py).
5. **Retry** — webhook доставляется до 3 попыток с экспоненциальной
   задержкой (`base * 2**(n-1)`) — [payments/services/webhook.py](payments/services/webhook.py).
6. **Dead Letter Queue** — настроена через `x-dead-letter-exchange` на
   очереди `payments.new`; consumer также явно публикует в DLQ при
   окончательной неудаче доставки webhook — [payments/broker.py](payments/broker.py).
7. **Идемпотентность** — уникальный `idempotency_key` защищает от дублей
   при создании; consumer не переобрабатывает уже обработанный платёж.
8. **Аутентификация** — статический ключ `X-API-Key` на всех эндпоинтах
   ([payments/common/utils/security.py](payments/common/utils/security.py)).
9. **Docker** — `postgres`, `rabbitmq`, `migrate`, `api`, `consumer`
   ([docker/docker-compose.yml](docker/docker-compose.yml)).

## Запуск через Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

Поднимутся:

- PostgreSQL — `localhost:5432`
- RabbitMQ — AMQP `localhost:5672`, Management UI `http://localhost:15672`
  (guest/guest)
- API — `http://localhost:8000` (Swagger: `http://localhost:8000/docs`)
- Consumer — обработчик очереди

Миграции применяет одноразовый сервис `migrate` до старта `api`/`consumer`.

## Примеры запросов

Все запросы требуют заголовок `X-API-Key: supersecret-api-key`.

### 1. Создание платежа

```bash
curl -i -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: supersecret-api-key" \
  -H "Idempotency-Key: 7e1d2c9a-0001" \
  -H "Content-Type: application/json" \
  -d '{
        "amount": "199.90",
        "currency": "RUB",
        "description": "Подписка Pro",
        "metadata": {"order_id": 42},
        "webhook_url": "https://webhook.site/your-uuid"
      }'
```

Ответ `202 Accepted`:

```json
{
  "payment_id": "f0e1...-...",
  "status": "pending",
  "created_at": "2026-06-22T10:00:00+00:00"
}
```

Повторный запрос с тем же `Idempotency-Key` вернёт тот же платёж
(`200 OK`), новый платёж не создаётся.

### 2. Получение платежа

```bash
curl http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: supersecret-api-key"
```

```json
{
  "id": "f0e1...",
  "amount": "199.90",
  "currency": "RUB",
  "description": "Подписка Pro",
  "metadata": {"order_id": 42},
  "status": "succeeded",
  "idempotency_key": "7e1d2c9a-0001",
  "webhook_url": "https://webhook.site/your-uuid",
  "created_at": "2026-06-22T10:00:00+00:00",
  "processed_at": "2026-06-22T10:00:03+00:00"
}
```

Через 2–5 секунд статус станет `succeeded` (90%) или `failed` (10%), и на
`webhook_url` уйдёт уведомление.

### Куда слать webhook

- Внешний сервис: [webhook.site](https://webhook.site) — удобно посмотреть
  доставку.
- Локально: запустите приёмник и используйте
  `http://host.docker.internal:9000/webhook` в качестве `webhook_url`:

  ```bash
  python tools/webhook_receiver.py 9000
  ```

### Проверка retry → DLQ

Укажите заведомо недоступный `webhook_url`
(например `http://127.0.0.1:1/webhook`). Consumer сделает 3 попытки с
задержками 1с и 2с, после чего сообщение уйдёт в очередь `payments.dlq` —
её видно в RabbitMQ Management UI (`http://localhost:15672`).

## Локальная разработка (без Docker)

```bash
poetry install
cp .env.example .env   # поправьте host'ы на localhost

# нужны запущенные PostgreSQL и RabbitMQ
poetry run alembic upgrade head
poetry run uvicorn payments.main:create_app --factory --reload   # терминал 1: API
poetry run faststream run payments.consumer.app:payments         # терминал 2: consumer
```
