import datetime

from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict


def json_schema_extra(schema: dict[str, Any]) -> None:
    """Формирование корректных примеров для приведенных типов."""
    for prop in schema.get('properties', {}).values():
        if prop.get('format') == 'date-time':
            prop['example'] = '%Y-%m-%dT%H:%M:%SZ'
        elif prop.get('format') == 'date':
            prop['example'] = '%Y-%m-%d'
        elif prop.get('type') == 'number' and 'format' not in prop:
            prop['example'] = '"0.00"'


def encode_datetime(value: datetime.datetime) -> str:
    """Приведение объекта datetime к корректному формату."""
    template = '%Y-%m-%dT%H:%M:%S'
    if value.tzinfo is not None and value.utcoffset() == datetime.timedelta(0):
        template = '%Y-%m-%dT%H:%M:%SZ'

    return value.strftime(template)


class JSONModel(BaseModel):
    """Класс базовой модели для корректной отдачи ответа сервиса в формате JSON."""

    model_config = ConfigDict(
        json_encoders={
            datetime.datetime: encode_datetime,
            datetime.date: lambda ob: ob.strftime('%Y-%m-%d'),
        },
        json_schema_extra=json_schema_extra,
    )
