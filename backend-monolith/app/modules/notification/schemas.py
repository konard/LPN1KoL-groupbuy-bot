from pydantic import BaseModel


class NotifyRequest(BaseModel):
    user_id: str
    type: str  # email | push | telegram | websocket
    payload: dict
