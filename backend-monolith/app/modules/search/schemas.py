from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, description="Поисковый запрос", example="мука пшеничная")
    page: int = Field(1, ge=1, description="Номер страницы")
    per_page: int = Field(20, ge=1, le=100, description="Количество результатов на странице")


class SearchResult(BaseModel):
    id: str = Field(..., description="Идентификатор закупки")
    score: float = Field(..., description="Релевантность результата")
    title: str = Field("", description="Название товара/закупки")
    description: str = Field("", description="Описание закупки")
    status: str = Field("", description="Статус закупки")
    highlights: dict[str, str] = Field({}, description="Фрагменты текста с подсветкой совпадений")


class SearchResponse(BaseModel):
    total: int = Field(..., description="Общее количество результатов")
    items: list[SearchResult] = Field(..., description="Список результатов поиска")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total": 1,
                "items": [
                    {
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "score": 1.5,
                        "title": "Мука пшеничная высший сорт",
                        "description": "Групповая закупка муки",
                        "status": "active",
                        "highlights": {"title": "<em>Мука пшеничная</em> высший сорт"},
                    }
                ],
            }
        }
    }
