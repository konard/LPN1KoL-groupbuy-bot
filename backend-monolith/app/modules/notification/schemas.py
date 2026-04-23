from pydantic import BaseModel, Field


class NotifyRequest(BaseModel):
    user_id: str = Field(..., description="Идентификатор пользователя-получателя уведомления")
    type: str = Field(..., description="Тип уведомления: email | push | telegram | websocket", example="email")
    payload: dict = Field(..., description="Данные уведомления (зависят от типа)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "type": "email",
                "payload": {"subject": "Новое уведомление", "body": "Ваш запрос был принят"},
            }
        }
    }
