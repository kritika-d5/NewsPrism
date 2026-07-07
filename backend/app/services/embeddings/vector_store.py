from typing import List, Dict, Optional
from app.core.config import settings
import uuid
import time

try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    Pinecone = None


class VectorStore:
    def __init__(self):
        self.index = None
        self.index_name = settings.PINECONE_INDEX_NAME
        
        if PINECONE_AVAILABLE and settings.PINECONE_API_KEY:
            try:
                pc = Pinecone(api_key=settings.PINECONE_API_KEY)
                self._ensure_index(pc)
                self.index = pc.Index(self.index_name)
            except Exception as e:
                print(f"Warning: Pinecone initialization failed: {e}")
                self.index = None
    
    def _ensure_index(self, pc):
        try:
            existing_indexes = [index.name for index in pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                print(f"Creating new Pinecone index: {self.index_name}")
                pc.create_index(
                    name=self.index_name,
                    dimension=settings.EMBEDDING_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                time.sleep(10)
        except Exception as e:
            print(f"Warning: Could not ensure Pinecone index exists: {e}")
    
    def upsert_vectors(
        self,
        vectors: List[Dict],
        namespace: Optional[str] = None
    ):
        if not vectors or not self.index:
            return
        
        pinecone_vectors = []
        for vec in vectors:
            pinecone_vectors.append({
                "id": vec.get("id", str(uuid.uuid4())),
                "values": vec["values"],
                "metadata": vec.get("metadata", {})
            })
        
        batch_size = 100
        for i in range(0, len(pinecone_vectors), batch_size):
            batch = pinecone_vectors[i:i + batch_size]
            try:
                self.index.upsert(vectors=batch, namespace=namespace)
            except Exception as e:
                print(f"Error upserting batch: {e}")
    
    def query_vectors(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict] = None,
        namespace: Optional[str] = None
    ) -> List[Dict]:
        if not self.index:
            return []
            
        try:
            results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=filter,
                namespace=namespace
            )
            
            return [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata
                }
                for match in results.matches
            ]
        except Exception as e:
            print(f"Error querying vectors: {e}")
            return []
    
    def delete_vectors(
        self,
        ids: List[str],
        namespace: Optional[str] = None
    ):
        if ids and self.index:
            try:
                self.index.delete(ids=ids, namespace=namespace)
            except Exception as e:
                print(f"Error deleting vectors: {e}")
    
    def delete_by_filter(
        self,
        filter: Dict,
        namespace: Optional[str] = None
    ):
        if self.index:
            try:
                self.index.delete(filter=filter, namespace=namespace)
            except Exception as e:
                print(f"Error deleting by filter: {e}")