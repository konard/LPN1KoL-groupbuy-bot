from pydantic import BaseModel


class SearchRequest(BaseModel):
    q: str
    page: int = 1
    per_page: int = 20


class SearchResult(BaseModel):
    id: str
    score: float
    title: str = ""
    description: str = ""
    status: str = ""
    highlights: dict[str, str] = {}


class SearchResponse(BaseModel):
    total: int
    items: list[SearchResult]
