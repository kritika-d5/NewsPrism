from typing import List, Dict, Optional, Any
import numpy as np
from sklearn.cluster import DBSCAN
from app.services.embeddings.embedding_service import EmbeddingService
from app.core.config import settings


class ClusteringService:
    """Groups articles that cover the same underlying event.

    Articles are embedded locally with SentenceTransformers and grouped with
    DBSCAN on cosine distance. This is fully self-contained: it does not depend
    on any external vector database being pre-populated.
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()

    def _article_text_for_embedding(self, article: Dict[str, Any]) -> str:
        title = (article.get("title") or "").strip()
        body = (article.get("text") or "").strip()
        # Title carries the strongest event signal; give it weight by prepending
        # it, then add the lead of the body which usually restates the event.
        combined = f"{title}. {body[:1500]}".strip()
        return combined or title or body

    def cluster_articles(
        self,
        query: str,
        articles: List[Dict[str, Any]],
        min_samples: Optional[int] = None,
        eps: Optional[float] = None,
    ) -> Dict[str, List[str]]:
        """Return a mapping of ``cluster_label -> [article_id, ...]``.

        Only articles carrying non-empty text are considered. Noise points
        (DBSCAN label -1) are attached to their nearest dense cluster when one
        exists, otherwise dropped as singletons.
        """
        usable = [
            a for a in articles
            if str(a.get("id") or a.get("_id")) and (a.get("text") or a.get("title"))
        ]

        if len(usable) < 2:
            if len(usable) == 1:
                only_id = str(usable[0].get("id") or usable[0].get("_id"))
                return {"cluster_0": [only_id]}
            return {}

        ids = [str(a.get("id") or a.get("_id")) for a in usable]
        texts = [self._article_text_for_embedding(a) for a in usable]

        embeddings = np.array(
            self.embedding_service.embed_batch(texts), dtype=np.float32
        )

        min_samples = min_samples or settings.CLUSTERING_MIN_SAMPLES
        eps = eps or settings.CLUSTERING_EPS

        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        labels = clustering.fit_predict(embeddings)

        # If DBSCAN found no dense region at all (everything noise), relax once
        # so we still surface at least one comparison cluster for the user.
        if not any(l != -1 for l in labels):
            clustering = DBSCAN(eps=min(0.9, eps + 0.2), min_samples=2, metric="cosine")
            labels = clustering.fit_predict(embeddings)
            if not any(l != -1 for l in labels):
                return {"cluster_0": ids}

        clusters: Dict[str, List[str]] = {}
        centroids: Dict[int, np.ndarray] = {}

        for label in sorted(set(labels)):
            if label == -1:
                continue
            member_idx = [i for i, l in enumerate(labels) if l == label]
            clusters[f"cluster_{label}"] = [ids[i] for i in member_idx]
            centroids[label] = embeddings[member_idx].mean(axis=0)

        # Re-home noise points into the nearest cluster if reasonably close.
        for i, label in enumerate(labels):
            if label != -1:
                continue
            if not centroids:
                continue
            best_label = None
            best_sim = -1.0
            for c_label, centroid in centroids.items():
                sim = float(
                    np.dot(embeddings[i], centroid)
                    / ((np.linalg.norm(embeddings[i]) * np.linalg.norm(centroid)) or 1.0)
                )
                if sim > best_sim:
                    best_sim = sim
                    best_label = c_label
            if best_label is not None and best_sim >= (1.0 - min(0.9, eps + 0.2)):
                clusters[f"cluster_{best_label}"].append(ids[i])

        return clusters

    def find_canonical_article(
        self,
        article_ids: List[str],
        articles_data: List[Dict],
    ) -> Optional[str]:
        if not article_ids or not articles_data:
            return None

        best_score = -1.0
        best_article_id = None

        for article in articles_data:
            if article.get("id") not in article_ids:
                continue

            score = 0.0
            text_length = len(article.get("text", ""))
            score += min(text_length / 1000, 1.0) * 0.3

            if article.get("author"):
                score += 0.2
            if article.get("published_at"):
                score += 0.2

            if score > best_score:
                best_score = score
                best_article_id = article.get("id")

        return best_article_id or article_ids[0]
