import logging
from typing import List, Optional

from openai import OpenAI
from pinecone import Pinecone

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBED_MODEL = "moonshot-v1-embed"
EMBED_DIM = 1536
POSTS_NAMESPACE = "posts"


class EmbeddingService:
    def __init__(self):
        self._openai_client: Optional[OpenAI] = None
        self._pinecone_index = None

    @property
    def openai_client(self) -> OpenAI:
        if self._openai_client is None:
            self._openai_client = OpenAI(
                api_key=settings.moonshot_api_key,
                base_url="https://api.moonshot.cn/v1",
            )
        return self._openai_client

    @property
    def pinecone_index(self):
        if self._pinecone_index is None:
            pc = Pinecone(api_key=settings.pinecone_api_key)
            self._pinecone_index = pc.index(settings.pinecone_index)
        return self._pinecone_index

    def embed_text(self, text: str) -> List[float]:
        response = self.openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=[text],
        )
        return response.data[0].embedding

    def upsert_post(
        self, post_id: str, user_id: str, username: str, caption: str
    ) -> None:
        try:
            vector = self.embed_text(f"{username}: {caption}")
            self.pinecone_index.upsert(
                vectors=[(post_id, vector, {"post_id": post_id, "user_id": user_id})],
                namespace=POSTS_NAMESPACE,
            )
        except Exception as e:
            logger.error(f"Failed to upsert post vector {post_id}: {e}")

    def search_posts(self, query: str, limit: int = 10) -> List[str]:
        try:
            vector = self.embed_text(query)
            results = self.pinecone_index.query(
                vector=vector,
                top_k=limit,
                namespace=POSTS_NAMESPACE,
                include_metadata=False,
            )
            return [match.id for match in results.matches]
        except Exception as e:
            logger.error(f"Failed to search post vectors: {e}")
            return []

    def delete_post_vector(self, post_id: str) -> None:
        try:
            self.pinecone_index.delete(ids=[post_id], namespace=POSTS_NAMESPACE)
        except Exception as e:
            logger.error(f"Failed to delete post vector {post_id}: {e}")


embedding_service = EmbeddingService()
