import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class VectorSearchResult(BaseModel):
    id: str
    score: float
    payload: Dict[str, Any]
    vector: Optional[List[float]] = None


class VectorStoreAdapter(ABC):
    @abstractmethod
    async def search(
        self, collection: str, vector: List[float], limit: int = 5, score_threshold: float = 0.0
    ) -> List[VectorSearchResult]:
        pass

    @abstractmethod
    async def upsert(self, collection: str, points: List[Any]):
        pass

    @abstractmethod
    async def delete_by_payload_filter(self, collection: str, key: str, value_lt: Any):
        pass


class QdrantAdapter(VectorStoreAdapter):
    def __init__(self, host: str, port: int, api_key: Optional[str] = None):
        from qdrant_client import QdrantClient

        # Async client is better for production, but using sync for compatibility with current env mostly
        # Switching to AsyncQdrantClient if possible
        try:
            from qdrant_client import AsyncQdrantClient

            self.client = AsyncQdrantClient(host=host, port=port, api_key=api_key)
        except ImportError:
            self.client = QdrantClient(host=host, port=port, api_key=api_key)

    async def search(
        self, collection: str, vector: List[float], limit: int = 5, score_threshold: float = 0.0
    ) -> List[VectorSearchResult]:
        args = {
            "collection_name": collection,
            "query_vector": vector,
            "limit": limit,
            "score_threshold": score_threshold,
            "with_payload": True,
        }

        if inspect.iscoroutinefunction(self.client.search):
            results = await self.client.search(**args)
        else:
            results = self.client.search(**args)

        return [VectorSearchResult(id=str(hit.id), score=hit.score, payload=hit.payload or {}) for hit in results]

    async def upsert(self, collection: str, points: List[Any]):
        if inspect.iscoroutinefunction(self.client.upsert):
            await self.client.upsert(collection_name=collection, points=points)
        else:
            # Sync client
            self.client.upsert(collection_name=collection, points=points)

    async def delete_by_payload_filter(self, collection: str, key: str, value_lt: Any):
        from qdrant_client.http import models

        filter = models.Filter(
            must=[
                models.FieldCondition(
                    key=key,
                    range=models.Range(lt=value_lt),
                )
            ]
        )
        
        if inspect.iscoroutinefunction(self.client.delete):
            await self.client.delete(collection_name=collection, points_selector=filter)
        else:
            self.client.delete(collection_name=collection, points_selector=filter)
