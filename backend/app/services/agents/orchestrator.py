import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx
from bson import ObjectId

EmitFn = Callable[[Dict[str, Any]], Awaitable[None]]

from app.core.config import settings
from app.core.database import get_database
from app.services.bias.bias_analyzer import BiasAnalyzer
from app.services.bias.omission_detector import OmissionDetector
from app.services.clustering.clustering_service import ClusteringService
from app.services.facts.fact_extractor import FactExtractor
from app.services.ingestion.ingestion_service import IngestionService


@dataclass
class ManagerState:
    query: str
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sources: Optional[List[str]] = None

    search_query: str = ""
    limit: int = 50
    attempt: int = 0

    news_category: str = "HardNews"

    articles: List[Dict[str, Any]] = field(default_factory=list)
    clusters: Dict[str, List[str]] = field(default_factory=dict)

    cluster_fact_payloads: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    bias_payloads: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    bias_weights: Dict[str, float] = field(default_factory=dict)

    @property
    def has_facts(self) -> bool:
        return bool(self.cluster_fact_payloads)

    @property
    def has_bias(self) -> bool:
        return bool(self.bias_payloads)


class AgentOrchestrator:
    # Human-readable identities for each agent in the newsroom pipeline.
    AGENTS = {
        "orchestrator": "Editor-in-Chief",
        "ingestor": "Ingestor / Scraper",
        "researcher": "Researcher",
        "clustering": "Story Clusterer",
        "fact_checker": "Fact-Checker",
        "bias_auditor": "Bias Auditor",
        "editor": "Copy Editor",
    }

    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_api_url = settings.GROQ_API_URL

        self.ingestion_service = IngestionService()
        self.clustering_service = ClusteringService()
        self.bias_analyzer = BiasAnalyzer()
        self.omission_detector = OmissionDetector()
        self.fact_extractor = FactExtractor()

        self._emit: Optional[EmitFn] = None

    async def emit(
        self,
        agent: str,
        status: str,
        title: str,
        detail: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Push a live pipeline event to any attached listener (SSE stream).

        No-op when the orchestrator is invoked without a listener, so the
        non-streaming ``/analyze`` endpoint keeps working unchanged.
        """
        if not self._emit:
            return
        event = {
            "type": "agent",
            "agent": agent,
            "agent_name": self.AGENTS.get(agent, agent),
            "status": status,
            "title": title,
            "detail": detail,
            "data": data or {},
            "ts": datetime.utcnow().isoformat(),
        }
        try:
            await self._emit(event)
        except Exception:
            pass

    async def analyze_query(
        self,
        query: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sources: Optional[List[str]] = None,
        emit: Optional[EmitFn] = None,
    ) -> Dict:
        self._emit = emit
        state = ManagerState(
            query=query,
            date_from=date_from,
            date_to=date_to,
            sources=sources,
            search_query=query,
            limit=50,
        )

        db = get_database()
        try:
            await self.emit(
                "orchestrator", "start", "Assignment received",
                f'Editor-in-Chief planning coverage of "{query}".',
                {"query": query},
            )

            max_attempts = 3
            for attempt in range(max_attempts):
                state.attempt = attempt
                if attempt == 0:
                    await self.emit(
                        "ingestor", "working", "Gathering sources",
                        f'Searching news wire for "{state.search_query}" and scraping full text.',
                    )
                    state.articles = await self._tool_ingest(
                        state, state.search_query, state.sources, state.limit, state.articles
                    )
                    await self.emit(
                        "ingestor", "done", "Sources gathered",
                        f"Collected {len(state.articles)} articles from "
                        f"{self._count_sources(state.articles)} outlets.",
                        {"articles": len(state.articles),
                         "sources": self._count_sources(state.articles)},
                    )
                    state.news_category = await self._classify_news_category(query, sample_articles=state.articles[:5])
                    await self.emit(
                        "orchestrator", "info", "Desk assigned",
                        f"Story classified as {state.news_category}.",
                        {"news_category": state.news_category},
                    )
                else:
                    await self.emit(
                        "researcher", "working", "Widening the net",
                        "Coverage looks thin or one-sided — requesting more diverse sources.",
                    )
                    ingest_sources, search_query, limit = await self._researcher_request_more_sources(
                        state=state
                    )
                    state.sources = ingest_sources
                    state.search_query = search_query
                    state.limit = limit
                    await self.emit(
                        "researcher", "done", "New angle proposed",
                        f'Researcher re-queried as "{search_query}" (target {limit} articles).',
                        {"search_query": search_query, "limit": limit},
                    )
                    state.articles = await self._tool_ingest(state, state.search_query, state.sources, state.limit, state.articles)
                    await self.emit(
                        "ingestor", "done", "More sources gathered",
                        f"Now holding {len(state.articles)} articles from "
                        f"{self._count_sources(state.articles)} outlets.",
                        {"articles": len(state.articles),
                         "sources": self._count_sources(state.articles)},
                    )

                if len(state.articles) < 2:
                    await self.emit("orchestrator", "error", "Not enough coverage",
                                    "Fewer than two articles found for this query.")
                    return {"error": "No articles found"}

                await self.emit(
                    "clustering", "working", "Grouping stories",
                    "Embedding articles and running DBSCAN to group coverage of the same event.",
                )
                state.clusters = await self._tool_cluster(state.query, state.articles)
                if not state.clusters:
                    await self.emit("clustering", "error", "Clustering failed", "")
                    return {"error": "Clustering failed"}
                await self.emit(
                    "clustering", "done", "Stories grouped",
                    f"Formed {len(state.clusters)} event cluster(s) from {len(state.articles)} articles.",
                    {"clusters": len(state.clusters),
                     "sizes": {k: len(v) for k, v in state.clusters.items()}},
                )

                await self.emit(
                    "fact_checker", "working", "Verifying facts",
                    "Extracting candidate claims and cross-checking them across sources.",
                )
                state.cluster_fact_payloads = await self._tool_extract_facts(state.query, state.articles, state.clusters)
                if not state.cluster_fact_payloads:
                    await self.emit("fact_checker", "error", "No verifiable clusters",
                                    "No cluster had enough overlapping coverage to verify.")
                    return {"error": "Fact extraction failed"}

                evidence = self._compute_evidence_metrics(state)
                await self.emit(
                    "fact_checker", "done", "Facts verified",
                    f"{evidence['facts_supported']} supported, "
                    f"{evidence['facts_contradicted']} contradicted, "
                    f"{evidence['facts_unverified']} unverified.",
                    evidence,
                )

                if attempt < max_attempts - 1:
                    should_ingest_more = await self._fact_checker_should_ingest_more(evidence)
                    if should_ingest_more:
                        await self.emit(
                            "orchestrator", "info", "Sending it back",
                            "Evidence is thin or conflicting — looping back for more sources.",
                            {"attempt": attempt + 1},
                        )
                        continue

                await self.emit(
                    "bias_auditor", "working", "Weighting the Bias Index",
                    "Inferring how much tone, lexical bias, omission and consistency should count.",
                )
                state.bias_weights = await self._auditor_infer_weights(state, evidence)
                await self.emit(
                    "bias_auditor", "info", "Weights set",
                    self._describe_weights(state.bias_weights),
                    {"weights": state.bias_weights},
                )
                state.bias_payloads = await self._tool_analyze_bias(state)
                await self.emit(
                    "bias_auditor", "done", "Bias scored",
                    f"Computed a Bias Index for every source across {len(state.bias_payloads)} cluster(s).",
                    {"weights": state.bias_weights},
                )

                await self.emit("editor", "working", "Filing the report",
                                "Persisting clusters and preparing the dashboard.")
                result = await self._tool_finalize(state, db)
                await self.emit(
                    "editor", "done", "Report filed",
                    f"{len(result.get('clusters', []))} cluster(s) ready to read.",
                    {"clusters": len(result.get("clusters", []))},
                )
                return result

            return await self._tool_finalize(state, db)
        except Exception as e:
            print(f"Orchestration error: {e}")
            await self.emit("orchestrator", "error", "Pipeline error", str(e))
            raise

    @staticmethod
    def _count_sources(articles: List[Dict[str, Any]]) -> int:
        return len({a.get("source") for a in articles if a.get("source")})

    @staticmethod
    def _describe_weights(weights: Dict[str, float]) -> str:
        if not weights:
            return "Using default weights."
        top = max(weights.items(), key=lambda kv: kv[1])
        pct = {k: f"{round(v * 100)}%" for k, v in weights.items()}
        return (
            f"Prioritising {top[0]} — tone {pct.get('tone', '?')}, "
            f"lexical {pct.get('lexical', '?')}, omission {pct.get('omission', '?')}, "
            f"consistency {pct.get('consistency', '?')}."
        )

    def _dedupe_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        for a in articles:
            url = a.get("url")
            unique_key = url or str(a.get("_id")) or str(a.get("id"))
            if unique_key in seen:
                continue
            seen.add(unique_key)
            out.append(a)
        return out

    async def _tool_ingest(
        self,
        state: ManagerState,
        query_override: str,
        sources: Optional[List[str]],
        limit: int,
        existing_articles: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        existing_articles = existing_articles or []
        new_articles = await self.ingestion_service.ingest_from_query(
            query=query_override,
            date_from=state.date_from,
            date_to=state.date_to,
            sources=sources,
            limit=limit,
        )
        merged = existing_articles + (new_articles or [])
        return self._dedupe_articles(merged)

    async def _tool_cluster(self, query: str, articles: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        usable = [a for a in articles if (a.get("text") or a.get("title"))]
        return self.clustering_service.cluster_articles(query=query, articles=usable)

    def _articles_by_id(self, articles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for a in articles:
            a_id = str(a.get("id") or a.get("_id"))
            out[a_id] = a
        return out

    def _facts_metrics_from_payload(self, payloads: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        supported = 0
        contradicted = 0
        unverified = 0
        total = 0
        for _, p in payloads.items():
            facts = p.get("facts") or []
            for f in facts:
                total += 1
                status = (f.get("status") or "").lower()
                if status == "supported":
                    supported += 1
                elif status == "contradicted":
                    contradicted += 1
                else:
                    unverified += 1
        return {
            "supported": supported,
            "contradicted": contradicted,
            "unverified": unverified,
            "total": total,
        }

    def _compute_evidence_metrics(self, state: ManagerState) -> Dict[str, Any]:
        articles_count = len(state.articles)
        unique_sources = len({a.get("source") for a in state.articles if a.get("source")})
        metrics = self._facts_metrics_from_payload(state.cluster_fact_payloads)
        total = metrics["total"] or 1
        contradiction_ratio = metrics["contradicted"] / total
        unverified_ratio = metrics["unverified"] / total
        return {
            "articles_count": articles_count,
            "unique_sources": unique_sources,
            "facts_supported": metrics["supported"],
            "facts_contradicted": metrics["contradicted"],
            "facts_unverified": metrics["unverified"],
            "contradiction_ratio": contradiction_ratio,
            "unverified_ratio": unverified_ratio,
        }

    async def _tool_extract_facts(
        self,
        query: str,
        articles: List[Dict[str, Any]],
        clusters: Dict[str, List[str]],
    ) -> Dict[str, Dict[str, Any]]:
        articles_map = self._articles_by_id(articles)
        cluster_payloads: Dict[str, Dict[str, Any]] = {}

        for cluster_label, cluster_article_ids in clusters.items():
            cluster_articles = [articles_map[i] for i in cluster_article_ids if i in articles_map]
            cluster_articles = [a for a in cluster_articles if (a.get("text") or "").strip()]
            if len(cluster_articles) < 2:
                continue

            await self.emit(
                "fact_checker", "working", "Cross-checking a cluster",
                f"Verifying claims across {len(cluster_articles)} articles covering the same event.",
                {"cluster": cluster_label, "articles": len(cluster_articles)},
            )

            articles_data = [
                {
                    "id": str(a.get("id") or a.get("_id")),
                    "text": a.get("text", ""),
                    "url": a.get("url", ""),
                    "source": a.get("source", "Unknown"),
                }
                for a in cluster_articles
            ]

            facts = await self.fact_extractor.extract_facts_from_articles(articles_data, query=query)
            if not facts:
                continue

            fact_summary = await self._generate_fact_summary(facts)
            fact_emotion = await self._get_fact_emotion(fact_summary)

            cluster_payloads[cluster_label] = {
                "cluster_article_ids": [str(a.get("id") or a.get("_id")) for a in cluster_articles],
                "cluster_articles": cluster_articles,
                "articles_data": articles_data,
                "facts": facts,
                "fact_summary": fact_summary,
                "fact_emotion": fact_emotion,
            }

        return cluster_payloads

    async def _tool_analyze_bias(self, state: ManagerState) -> Dict[str, Dict[str, Any]]:
        bias_payloads: Dict[str, Dict[str, Any]] = {}
        for cluster_label, payload in state.cluster_fact_payloads.items():
            cluster_articles: List[Dict[str, Any]] = payload.get("cluster_articles") or []
            facts: List[Dict[str, Any]] = payload.get("facts") or []
            fact_emotion: float = float(payload.get("fact_emotion") or 0.0)
            if len(cluster_articles) < 2 or not facts:
                continue

            bias_features: List[Dict[str, Any]] = []
            tone_scores: List[float] = []

            for a in cluster_articles:
                article_id = str(a.get("id") or a.get("_id"))
                article_text = a.get("text", "")

                bias_analysis = self.bias_analyzer.analyze_article(article_text)
                omission_result = self.omission_detector.detect_omissions(
                    cluster_facts=facts,
                    article_text=article_text,
                    article_id=article_id,
                )

                tone_score = float(bias_analysis.get("tone_score") or 0.0)
                lexical_bias = float(bias_analysis.get("lexical_bias_score") or 0.0)
                omission_score = float(omission_result.get("omission_score") or 0.0)
                subjectivity_score = float(bias_analysis.get("subjectivity_score") or 0.0)
                consistency_score = max(0.0, min(1.0, 0.6 * omission_score + 0.4 * subjectivity_score))

                tone_scores.append(tone_score)
                bias_features.append(
                    {
                        "article_id": article_id,
                        "source": a.get("source", "Unknown"),
                        "tone": tone_score,
                        "lexical_bias": lexical_bias,
                        "omission_score": omission_score,
                        "consistency_score": consistency_score,
                        "subjectivity_score": subjectivity_score,
                        "loaded_phrases": bias_analysis.get("loaded_phrases") or [],
                    }
                )

            cluster_mean_tone = sum(tone_scores) / len(tone_scores) if tone_scores else 0.0

            omission_avg = sum(f["omission_score"] for f in bias_features) / len(bias_features) if bias_features else 0.0
            weights = self._auditor_self_correct_weights(state.bias_weights, omission_avg)

            if weights != state.bias_weights:
                state.bias_weights = weights

            bias_results: List[Dict[str, Any]] = []
            for idx, f in enumerate(bias_features):
                bias_index = self.bias_analyzer.compute_bias_index(
                    tone_score=f["tone"],
                    lexical_bias=f["lexical_bias"],
                    omission_score=f["omission_score"],
                    consistency_score=f["consistency_score"],
                    cluster_mean_tone=cluster_mean_tone,
                    fact_emotion=fact_emotion,
                    weights=state.bias_weights,
                )
                transparency = self.bias_analyzer.compute_transparency_score(
                    omission_score=f["omission_score"],
                    consistency_score=f["consistency_score"],
                    lexical_bias=f["lexical_bias"],
                    weights=state.bias_weights,
                )

                loaded_phrases_with_alternatives = await self._add_phrase_alternatives(f["loaded_phrases"])
                bias_results.append(
                    {
                        "article_id": f["article_id"],
                        "source": f["source"],
                        "tone": f["tone"],
                        "lexical_bias": f["lexical_bias"],
                        "omission_score": f["omission_score"],
                        "consistency_score": f["consistency_score"],
                        "bias_index": bias_index,
                        "transparency_score": transparency,
                        "loaded_phrases": loaded_phrases_with_alternatives,
                        "missing_facts": [],
                    }
                )

            frame_summary = self._generate_frame_summary(bias_results)
            canonical_id = self.clustering_service.find_canonical_article(
                article_ids=[str(i) for i in payload.get("cluster_article_ids") or []],
                articles_data=payload.get("articles_data") or [],
            )

            bias_payloads[cluster_label] = {
                "cluster_article_ids": payload.get("cluster_article_ids") or [],
                "canonical_article_id": canonical_id,
                "bias_results": bias_results,
                "frame_summary": frame_summary,
            }

        return bias_payloads

    def _auditor_self_correct_weights(self, weights: Dict[str, float], omission_avg: float) -> Dict[str, float]:
        weights = dict(weights or {})
        if not weights:
            return weights

        if omission_avg < 0.2 and weights.get("omission", 0.0) > 0.35:
            dec = weights["omission"] * 0.7
            delta = weights["omission"] - dec
            weights["omission"] = dec
            rest = weights.get("tone", 0.0) + weights.get("lexical", 0.0) + weights.get("consistency", 0.0)
            if rest > 0:
                for k in ["tone", "lexical", "consistency"]:
                    weights[k] = weights.get(k, 0.0) + delta * (weights.get(k, 0.0) / rest)

        s = sum(weights.values()) or 1.0
        return {k: v / s for k, v in weights.items()}

    async def _tool_finalize(self, state: ManagerState, db) -> Dict[str, Any]:
        if not state.bias_payloads:
            return {"query": state.query, "total_articles": len(state.articles), "clusters": []}

        articles_map = self._articles_by_id(state.articles)
        cluster_results: List[Dict[str, Any]] = []

        for cluster_label, payload in state.bias_payloads.items():
            cluster_fact_payload = state.cluster_fact_payloads.get(cluster_label) or {}
            cluster_articles_data = cluster_fact_payload.get("articles_data") or []
            facts = cluster_fact_payload.get("facts") or []
            frame_summary = payload.get("frame_summary") or []

            insert_doc = {
                "query": state.query,
                "created_at": datetime.utcnow(),
                "fact_summary": cluster_fact_payload.get("fact_summary"),
                "frame_summary": frame_summary,
                "facts": facts,
                "canonical_article_id": payload.get("canonical_article_id"),
                "fact_emotion": cluster_fact_payload.get("fact_emotion", 0.0),
                "news_category": state.news_category,
                "bias_weights": state.bias_weights or {},
            }

            cluster_result = await db.clusters.insert_one(insert_doc)
            inserted_cluster_id = str(cluster_result.inserted_id)

            for article_id in payload.get("cluster_article_ids") or []:
                a = articles_map.get(str(article_id))
                if not a:
                    continue
                for br in payload.get("bias_results") or []:
                    if br.get("article_id") == str(article_id):
                        await db.articles.update_one(
                            {"_id": ObjectId(str(article_id))},
                            {
                                "$set": {
                                    "tone_score": br.get("tone"),
                                    "lexical_bias_score": br.get("lexical_bias"),
                                    "omission_score": br.get("omission_score"),
                                    "consistency_score": br.get("consistency_score"),
                                    "bias_index": br.get("bias_index"),
                                    "cluster_id": inserted_cluster_id,
                                }
                            },
                        )
                        break

            cluster_results.append(
                {
                    "cluster_id": inserted_cluster_id,
                    "articles_count": len(payload.get("cluster_article_ids") or []),
                    "facts_count": len(facts),
                    "bias_results": payload.get("bias_results") or [],
                }
            )

        return {"query": state.query, "total_articles": len(state.articles), "clusters": cluster_results}

    async def _researcher_request_more_sources(self, state: ManagerState) -> Tuple[Optional[List[str]], str, int]:
        evidence = self._compute_evidence_metrics(state)
        prompt = f"""You are the Researcher agent. Decide how to improve source diversity to reduce bias.

Return ONLY JSON with keys:
1) "query_override": string
2) "sources": array of strings or null
3) "limit_multiplier": number (>=1)

Constraints:
- If you need opposing perspectives, include terms like "opposition", "counter", "critics", "analysis", or "debate".
- Prefer null sources to broaden if the system currently used few sources.

State:
query: {state.query}
news_category: {state.news_category}
articles_count: {evidence['articles_count']}
unique_sources: {evidence['unique_sources']}
contradiction_ratio: {evidence['contradiction_ratio']}
unverified_ratio: {evidence['unverified_ratio']}
"""
        decision = await self._groq_json(prompt, max_tokens=180, temperature=0.2)

        query_override = decision.get("query_override") or state.query
        sources = decision.get("sources")
        limit_multiplier = decision.get("limit_multiplier") or 1.5
        if not isinstance(limit_multiplier, (int, float)):
            limit_multiplier = 1.5

        limit = int(max(20, round(state.limit * float(limit_multiplier))))
        return (sources, query_override, limit)

    async def _fact_checker_should_ingest_more(self, evidence: Dict[str, Any]) -> bool:
        uniq_sources = int(evidence.get("unique_sources") or 0)
        contradiction_ratio = float(evidence.get("contradiction_ratio") or 0.0)
        unverified_ratio = float(evidence.get("unverified_ratio") or 0.0)

        tools_spec = {
            "ingestor": {
                "description": "Search and scrape articles for the query.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "date_from": {"type": ["string", "null"]},
                        "date_to": {"type": ["string", "null"]},
                        "sources": {"type": ["array", "null"], "items": {"type": "string"}},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["query", "limit"],
                },
            },
            "fact_checker": {
                "description": "Extract and verify factual claims from a list of articles.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "articles": {"type": "array"},
                        "query": {"type": "string"},
                    },
                    "required": ["articles"],
                },
            },
            "bias_inspector": {
                "description": "Compute bias components (tone/lexical/omission/consistency) per article.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "article_text": {"type": "string"},
                        "verified_facts": {"type": "array"},
                        "weights": {"type": "object"},
                    },
                    "required": ["article_text", "verified_facts"],
                },
            },
            "editor": {
                "description": "Consolidate results into cluster response and persist to DB.",
                "input_schema": {"type": "object"},
            },
        }

        prompt = f"""You are the Manager agent deciding the next tool action.

Tool catalog (schemas only):
{json.dumps(tools_spec)}

Evidence summary:
articles_count: {evidence['articles_count']}
unique_sources: {evidence['unique_sources']}
facts_supported: {evidence['facts_supported']}
facts_contradicted: {evidence['facts_contradicted']}
facts_unverified: {evidence['facts_unverified']}
contradiction_ratio: {evidence['contradiction_ratio']}
unverified_ratio: {evidence['unverified_ratio']}

Decide whether we should ingest more articles to improve coverage/diversity before computing bias.
Return ONLY JSON: {{"action": "ingest_more" | "proceed"}}

Rules:
- If unique_sources < 4 ingest_more.
- If contradiction_ratio > 0.25 OR unverified_ratio > 0.45 ingest_more.
Otherwise proceed.
"""
        decision = await self._groq_json(prompt, max_tokens=80, temperature=0.1)
        action = (decision.get("action") or "").strip()
        if action == "ingest_more":
            return True
        if action == "proceed":
            return False

        if uniq_sources < 4:
            return True
        if contradiction_ratio > 0.25 or unverified_ratio > 0.45:
            return True
        return False

    async def _auditor_infer_weights(self, state: ManagerState, evidence: Dict[str, Any]) -> Dict[str, float]:
        sample = (state.articles or [])[:6]
        sample_features = []
        for a in sample:
            analysis = self.bias_analyzer.analyze_article(a.get("text", ""))
            sample_features.append(
                {
                    "source": a.get("source", "Unknown"),
                    "tone": analysis.get("tone_score", 0.0),
                    "lexical_bias": analysis.get("lexical_bias_score", 0.0),
                    "subjectivity": analysis.get("subjectivity_score", 0.0),
                }
            )

        prompt = f"""You are the Auditor agent. Infer dynamic weights for bias scoring.

You must output weights for: tone, lexical, omission, consistency.
They should sum to 1 and reflect what matters most for bias in this query.

If the topic looks like hard facts, prioritize omission/consistency.
If the topic looks opinionated, prioritize lexical/tone.
If evidence shows lots of contradictions or unverified claims, prioritize omission/consistency.

Return ONLY JSON with keys: tone, lexical, omission, consistency.

query: {state.query}
news_category: {state.news_category}
evidence:
- articles_count: {evidence['articles_count']}
- unique_sources: {evidence['unique_sources']}
- contradiction_ratio: {evidence['contradiction_ratio']}
- unverified_ratio: {evidence['unverified_ratio']}
sample_article_features: {json.dumps(sample_features)}
"""
        weights = await self._groq_json(prompt, max_tokens=120, temperature=0.2)

        out = {
            "tone": float(weights.get("tone", settings.BIAS_WEIGHT_TONE)),
            "lexical": float(weights.get("lexical", settings.BIAS_WEIGHT_LEXICAL)),
            "omission": float(weights.get("omission", settings.BIAS_WEIGHT_OMISSION)),
            "consistency": float(weights.get("consistency", settings.BIAS_WEIGHT_CONSISTENCY)),
        }
        s = sum(out.values()) or 1.0
        out = {k: v / s for k, v in out.items()}
        return out

    async def _groq_chat(self, system: Optional[str], user: str, temperature: float, max_tokens: int) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.groq_api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30.0,
            )
            if response.status_code != 200:
                return ""
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _groq_json(self, user_prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        system = "Return ONLY valid JSON. Do not include explanations."
        content = await self._groq_chat(system=system, user=user_prompt, temperature=temperature, max_tokens=max_tokens)
        if not content:
            return {}
        try:
            return json.loads(content)
        except Exception:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except Exception:
                    return {}
            return {}

    async def _classify_news_category(self, query: str, sample_articles: List[Dict[str, Any]]) -> str:
        sample_text = "\n".join([a.get("title", "")[:100] for a in sample_articles[:3]])
        prompt = f"""Classify this news query into one category: Breaking, Opinion, or HardNews.

Query: {query}
Sample headlines: {sample_text}

Respond with ONLY one word: Breaking, Opinion, or HardNews"""
        content = await self._groq_chat(system=None, user=prompt, temperature=0.1, max_tokens=10)
        category = (content or "").strip()
        if category in ["Breaking", "Opinion", "HardNews"]:
            return category
        return "HardNews"

    async def _generate_fact_summary(self, facts: List[Dict[str, Any]]) -> str:
        if not facts:
            return "No facts to summarize."

        facts_text = "\n".join([f"- {f.get('fact', '')[:200]}" for f in facts[:10]])
        prompt = f"""Summarize the following verified facts into a concise fact summary (3-5 sentences):

{facts_text}

Return only the summary, no additional commentary."""
        content = await self._groq_chat(system=None, user=prompt, temperature=0.1, max_tokens=300)
        return content or "Fact summary generation failed."

    async def _get_fact_emotion(self, fact_summary: str) -> float:
        if not fact_summary or fact_summary == "No facts to summarize.":
            return 0.0

        prompt = f"""Rate the emotional weight of these facts on a scale from -1 (very negative/tragic) to +1 (very positive/uplifting).

Facts: {fact_summary[:300]}

Respond with ONLY a number between -1 and 1."""
        content = await self._groq_chat(system=None, user=prompt, temperature=0.1, max_tokens=10)
        try:
            return float((content or "").strip())
        except Exception:
            return 0.0

    async def _add_phrase_alternatives(self, phrases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not phrases:
            return []

        enhanced_phrases: List[Dict[str, Any]] = []
        for phrase in phrases[:5]:
            original = phrase.get("phrase", "")
            phrase_type = phrase.get("type", "")
            # The keyword matcher upstream flags any sentence containing a
            # loaded word — including attributed facts ("According to UNICEF,
            # ... devastating injuries"). Let the LLM adjudicate: only keep
            # phrases where the OUTLET's own framing is loaded.
            prompt = f"""A keyword filter flagged this sentence from a news article as potentially biased.

Sentence: {original[:200]}
Flagged as: {phrase_type}

First decide: is this genuinely biased FRAMING chosen by the news outlet, or is it factual/attributed reporting (statistics, quotes or claims attributed to officials/organizations, plain description of events)? Attributed statements and verifiable statistics are FACTUAL even if the subject matter is emotional.

Respond in exactly this format:
VERDICT: [BIASED or FACTUAL]
REASON: [one line: why it is biased framing, or why it is factual reporting]
ALTERNATIVE: [neutral rewrite if BIASED, otherwise N/A]"""

            content = await self._groq_chat(system=None, user=prompt, temperature=0.2, max_tokens=180)
            if not content:
                # Can't adjudicate — err on the side of not accusing the outlet.
                continue

            verdict = ""
            reason = ""
            alternative = ""
            for line in content.split("\n"):
                if line.startswith("VERDICT:"):
                    verdict = line.replace("VERDICT:", "").strip().upper()
                elif line.startswith("REASON:"):
                    reason = line.replace("REASON:", "").strip()
                elif line.startswith("ALTERNATIVE:"):
                    alternative = line.replace("ALTERNATIVE:", "").strip()

            if "FACTUAL" in verdict:
                continue

            phrase["objective_alternative"] = alternative if alternative.upper() != "N/A" else original
            phrase["reason"] = reason or phrase.get("reason", "")
            enhanced_phrases.append(phrase)

        return enhanced_phrases

    def _generate_frame_summary(self, bias_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        frame_summaries: List[Dict[str, Any]] = []
        for result in bias_results:
            frame_summaries.append(
                {
                    "source": result.get("source"),
                    "tone": result.get("tone"),
                    "bias_index": result.get("bias_index"),
                    "transparency_score": result.get("transparency_score"),
                    "top_phrases": result.get("loaded_phrases", [])[:5],
                }
            )
        return frame_summaries

