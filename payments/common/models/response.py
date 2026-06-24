from pydantic import ConfigDict

from payments.common.utils.encoder import JSONModel


class BaseResponseModel(JSONModel):
    """Базовая модель Pydantic для валидации исходящего ответа."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            'by_alias': True,
        },
    )
