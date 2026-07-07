from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime
from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from bson import ObjectId
from pymongo import IndexModel


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string"}

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)
        raise ValueError("Invalid ObjectId type")
    
    def __str__(self):
        return str(super())
    
    def __repr__(self):
        return f"PyObjectId('{str(self)}')"


class Article(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    source: str
    url: str
    title: str
    author: Optional[str] = None
    published_at: datetime
    text: str
    raw_html: Optional[str] = None
    language: str = "en"
    country: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    
    chunks: Optional[List[Dict[str, Any]]] = None
    ner_entities: Optional[List[Dict[str, Any]]] = None
    
    tone_score: Optional[float] = None
    lexical_bias_score: Optional[float] = None
    omission_score: Optional[float] = None
    consistency_score: Optional[float] = None
    bias_index: Optional[float] = None
    
    cluster_id: Optional[str] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "source": "BBC News",
                "url": "https://example.com/article",
                "title": "Example Article",
                "published_at": "2024-01-01T00:00:00Z",
                "text": "Article content..."
            }
        }
    }


class Cluster(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    query: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    canonical_article_id: Optional[str] = None
    
    fact_summary: Optional[str] = None
    frame_summary: Optional[List[Dict[str, Any]]] = None
    facts: Optional[List[Dict[str, Any]]] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class ArticleAnalysis(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    article_id: str
    analysis_type: str
    result: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


ARTICLE_INDEXES = [
    IndexModel([("source", 1)]),
    IndexModel([("published_at", -1)]),
    IndexModel([("cluster_id", 1)]),
    IndexModel([("url", 1)], unique=True),
]

CLUSTER_INDEXES = [
    IndexModel([("query", 1)]),
    IndexModel([("created_at", -1)]),
]

ANALYSIS_INDEXES = [
    IndexModel([("article_id", 1)]),
    IndexModel([("analysis_type", 1)]),
]
