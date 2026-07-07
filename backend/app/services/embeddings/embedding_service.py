from typing import List, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from app.core.config import settings


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.dimension = settings.EMBEDDING_DIMENSION
    
    def embed_text(self, text: str) -> List[float]:
        embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings.tolist()
    
    def chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[dict]:
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            
            chunks.append({
                "text": chunk_text,
                "start": i,
                "end": min(i + chunk_size, len(words))
            })
        
        return chunks
    
    def embed_article(self, text: str, chunk_size: int = 512) -> List[dict]:
        chunks = self.chunk_text(text, chunk_size)
        
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embed_batch(texts)
        
        result = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            result.append({
                "chunk_id": f"chunk_{i}",
                "text": chunk["text"],
                "embedding": embedding,
                "start": chunk["start"],
                "end": chunk["end"]
            })
        
        return result

