FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

# Системные зависимости (для сборки asyncpg и пр.).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock* ./
RUN poetry install --only main --no-root

COPY . .

EXPOSE 8000

# Команда по умолчанию переопределяется в docker-compose для каждого сервиса (api / consumer / migrate).
CMD ["uvicorn", "payments.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
