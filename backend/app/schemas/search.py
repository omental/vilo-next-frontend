from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    id: int
    label: str
    context: str | None = None
    href: str


class GlobalSearchResponse(BaseModel):
    query: str
    groups: dict[str, list[SearchResultItem]] = Field(default_factory=dict)
