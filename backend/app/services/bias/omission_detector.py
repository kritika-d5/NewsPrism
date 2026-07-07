from typing import List, Dict
import numpy as np
from app.services.embeddings.embedding_service import EmbeddingService


class OmissionDetector:
    _fact_embedding_cache: Dict[str, List[float]] = {}

    def __init__(self):
        self.embedding_service = EmbeddingService()
    
    def detect_omissions(
        self,
        cluster_facts: List[Dict],
        article_text: str,
        article_id: str
    ) -> Dict:
        if not cluster_facts:
            return {
                "omission_score": 0.0,
                "missing_facts": [],
                "present_facts": []
            }

        cluster_facts = cluster_facts[:30]

        missing_facts: List[Dict] = []
        present_facts: List[Dict] = []

        try:
            article_text_norm = (article_text or "").strip()
            article_text_norm = article_text_norm[:20000]
            if not article_text_norm:
                raise ValueError("Empty article text")

            article_embedding = np.array(self.embedding_service.embed_text(article_text_norm), dtype=np.float32)

            for fact in cluster_facts:
                fact_text = (fact.get("fact") or "").strip()
                if not fact_text:
                    continue

                fact_key = fact_text.lower()
                if fact_key not in self._fact_embedding_cache:
                    self._fact_embedding_cache[fact_key] = self.embedding_service.embed_text(fact_text)
                    if len(self._fact_embedding_cache) > 2000:
                        self._fact_embedding_cache.clear()

                fact_embedding = np.array(self._fact_embedding_cache[fact_key], dtype=np.float32)
                similarity = float(np.dot(article_embedding, fact_embedding))

                if similarity >= 0.38:
                    present_facts.append(fact)
                else:
                    missing_facts.append(fact)
        except Exception:
            missing_facts, present_facts = self._detect_omissions_by_keywords(cluster_facts, article_text)

        omission_score = len(missing_facts) / len(cluster_facts) if cluster_facts else 0.0

        return {
            "omission_score": omission_score,
            "missing_facts": missing_facts,
            "present_facts": present_facts,
        }

    def _detect_omissions_by_keywords(self, cluster_facts: List[Dict], article_text: str) -> tuple[list[Dict], list[Dict]]:
        missing_facts: List[Dict] = []
        present_facts: List[Dict] = []

        article_lower = (article_text or "").lower()
        for fact in cluster_facts:
            fact_text = (fact.get("fact") or "").lower()
            fact_keywords = self._extract_keywords(fact_text)
            mentioned = any(keyword in article_lower for keyword in fact_keywords if len(keyword) > 3)
            if mentioned:
                present_facts.append(fact)
            else:
                missing_facts.append(fact)

        return missing_facts, present_facts

    def _extract_keywords(self, text: str) -> List[str]:
        words = text.split()
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
        }

        keywords = [w.lower().strip(".,!?;:") for w in words if w.lower() not in stop_words]
        return keywords[:10]

