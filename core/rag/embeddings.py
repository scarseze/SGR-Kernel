from abc import ABC, abstractmethod
from typing import List

import httpx


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        import os
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        if not self.base_url:
            raise ValueError("OLLAMA_BASE_URL must be provided.")
        self.model = model or os.getenv("EMBEDDING_MODEL")
        if not self.model:
            raise ValueError("EMBEDDING_MODEL must be provided.")

    async def embed(self, text: str, client: httpx.AsyncClient | None = None) -> List[float]:
        if client:
            return await self._do_embed(client, text)
        async with httpx.AsyncClient() as new_client:
            return await self._do_embed(new_client, text)

    async def _do_embed(self, client: httpx.AsyncClient, text: str) -> List[float]:
        response = await client.post(f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text})
        response.raise_for_status()
        return response.json()["embedding"]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        import asyncio
        
        async with httpx.AsyncClient() as client:
            return await asyncio.gather(*[self.embed(t, client=client) for t in texts])


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model

    async def embed(self, text: str) -> List[float]:
        # Placeholder for OpenAI implementation
        raise NotImplementedError("OpenAI embeddings not yet configured")

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("OpenAI embeddings not yet configured")
