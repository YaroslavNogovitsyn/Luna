from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel


class BaseRequestModel(BaseModel):
    """
    Базовая модель Pydantic для валидации тела входящего запроса.

    Автоматический преобразует имена входящих полей
    из формата camelCase в формат snake_case
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
