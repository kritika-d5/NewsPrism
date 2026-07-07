from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from uuid import UUID


def _coerce_date_bound(value: Any, *, end_of_day: bool) -> Any:
    """Accept bare dates ("2026-07-01") from HTML date inputs.

    Pydantic v2 requires a time component for datetime fields, so widen the
    accepted input here: a date-only string becomes midnight (for lower
    bounds) or 23:59:59 (for upper bounds, making the range inclusive).
    """
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return None
        if len(v) == 10:  # "YYYY-MM-DD"
            suffix = "T23:59:59" if end_of_day else "T00:00:00"
            return v + suffix
    return value


class ArticleBase(BaseModel):
    source: str
    url: str
    title: str
    author: Optional[str] = None
    published_at: datetime
    text: str
    language: str = "en"
    country: Optional[str] = None


class ArticleCreate(ArticleBase):
    raw_html: Optional[str] = None


class Chunk(BaseModel):
    chunk_id: str
    text: str
    embedding_id: Optional[str] = None
    start: int
    end: int


class NEREntity(BaseModel):
    entity: str
    type: str
    span: str


class ArticleResponse(ArticleBase):
    id: str  # Changed from UUID to str to support MongoDB ObjectIds
    scraped_at: datetime
    chunks: Optional[List[Chunk]] = None
    ner_entities: Optional[List[NEREntity]] = None
    tone_score: Optional[float] = None
    lexical_bias_score: Optional[float] = None
    omission_score: Optional[float] = None
    consistency_score: Optional[float] = None
    bias_index: Optional[float] = None
    cluster_id: Optional[str] = None  # Changed from Optional[UUID]
    missing_facts: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class ClusterBase(BaseModel):
    query: str


class Fact(BaseModel):
    fact: str
    sources: List[str]  # URLs
    quotes: List[str]
    status: str  # "supported", "contradicted", "unverified"


class FrameSummary(BaseModel):
    source: str
    tone: float
    top_phrases: List[Dict[str, Any]]
    transparency_score: float
    bias_index: float


class ClusterResponse(BaseModel):
    id: str  # Changed from UUID to str
    query: str
    created_at: datetime
    canonical_article_id: Optional[str] = None  # Changed from Optional[UUID]
    fact_summary: Optional[str] = None
    frame_summary: Optional[List[FrameSummary]] = None
    facts: Optional[List[Fact]] = None
    articles: List[ArticleResponse]
    news_category: Optional[str] = None
    fact_emotion: Optional[float] = None
    bias_weights: Optional[Dict[str, float]] = None

    class Config:
        from_attributes = True


class _DateRangeRequest(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    @field_validator("date_from", mode="before")
    @classmethod
    def _parse_date_from(cls, v):
        return _coerce_date_bound(v, end_of_day=False)

    @field_validator("date_to", mode="before")
    @classmethod
    def _parse_date_to(cls, v):
        return _coerce_date_bound(v, end_of_day=True)


class SearchRequest(_DateRangeRequest):
    query: str
    sources: Optional[List[str]] = None
    limit: int = 50


class AnalyzeRequest(_DateRangeRequest):
    query: str
    sources: Optional[List[str]] = None