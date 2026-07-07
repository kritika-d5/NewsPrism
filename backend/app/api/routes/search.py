import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Any, Dict, List
from app.core.database import get_database
from app.schemas.article import SearchRequest, ArticleResponse, ClusterResponse, AnalyzeRequest
from app.services.agents.orchestrator import AgentOrchestrator
from bson import ObjectId
from bson.errors import InvalidId

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=List[ArticleResponse])
async def search_articles(request: SearchRequest):
    db = get_database()
    query_pattern = {"$regex": request.query, "$options": "i"}
    
    cursor = db.articles.find({
        "$or": [
            {"title": query_pattern},
            {"text": query_pattern}
        ]
    }).limit(request.limit)
    
    articles = await cursor.to_list(length=request.limit)
    
    for article in articles:
        article["id"] = str(article["_id"])
    
    return articles


@router.post("/analyze")
async def analyze_query(request: AnalyzeRequest):
    orchestrator = AgentOrchestrator()
    
    try:
        result = await orchestrator.analyze_query(
            query=request.query,
            date_from=request.date_from,
            date_to=request.date_to,
            sources=request.sources
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/stream")
async def analyze_query_stream(request: AnalyzeRequest):
    """Run the agentic pipeline and stream each agent's progress as SSE.

    Emits ``data: {...}\\n\\n`` frames. Event ``type`` is one of:
    ``agent`` (a pipeline step), ``result`` (final payload), ``error`` or ``done``.
    """
    orchestrator = AgentOrchestrator()
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()

    async def emit(event: Dict[str, Any]) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            result = await orchestrator.analyze_query(
                query=request.query,
                date_from=request.date_from,
                date_to=request.date_to,
                sources=request.sources,
                emit=emit,
            )
            if isinstance(result, dict) and result.get("error"):
                await queue.put({"type": "error", "error": result["error"]})
            else:
                await queue.put({"type": "result", "result": result})
        except Exception as e:  # noqa: BLE001 - surface any failure to the client
            await queue.put({"type": "error", "error": str(e)})
        finally:
            await queue.put({"type": "done"})

    async def event_generator():
        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/clusters/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(cluster_id: str):
    db = get_database()
    
    try:
        cluster = await db.clusters.find_one({"_id": ObjectId(cluster_id)})
    except InvalidId:
        raise HTTPException(status_code=404, detail="Invalid cluster ID")
    
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    articles = await db.articles.find({"cluster_id": cluster_id}).to_list(length=100)
    
    cluster_facts = cluster.get("facts", [])
    if cluster_facts:
        from app.services.bias.omission_detector import OmissionDetector
        omission_detector = OmissionDetector()
        
        for article in articles:
            article["id"] = str(article["_id"])
            omission_result = omission_detector.detect_omissions(
                cluster_facts=cluster_facts,
                article_text=article.get("text", ""),
                article_id=article["id"]
            )
            article["missing_facts"] = omission_result.get("missing_facts", [])
    else:
        for article in articles:
            article["id"] = str(article["_id"])
            article["missing_facts"] = []
    
    cluster["id"] = str(cluster["_id"])
    cluster["articles"] = articles
    
    return cluster


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str):
    db = get_database()
    
    try:
        article = await db.articles.find_one({"_id": ObjectId(article_id)})
    except InvalidId:
        raise HTTPException(status_code=404, detail="Invalid article ID")
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    article["id"] = str(article["_id"])
    
    return article
