import logging
from typing import List

from pinecone import Pinecone

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBED_MODEL = "llama-text-embed-v2"
EMBED_DIM = 1024
POSTS_NAMESPACE = "posts"
USERS_NAMESPACE = "users"


class EmbeddingService:
    def __init__(self):
        self._pinecone = None
        self._pinecone_index = None

    @property
    def pinecone(self) -> Pinecone:
        if self._pinecone is None:
            self._pinecone = Pinecone(api_key=settings.pinecone_api_key)
        return self._pinecone

    @property
    def pinecone_index(self):
        if self._pinecone_index is None:
            self._pinecone_index = self.pinecone.Index(settings.pinecone_index)
        return self._pinecone_index

    def embed_text(self, text: str, input_type: str = "passage") -> List[float]:
        response = self.pinecone.inference.embed(
            model=EMBED_MODEL,
            inputs=[text],
            parameters={"input_type": input_type, "truncate": "END"},
        )
        return response.data[0]["values"]

    def upsert_post(self, post_id: str, user_id: str, username: str, caption: str) -> None:
        try:
            vector = self.embed_text(f"{username}: {caption}", input_type="passage")
            self.pinecone_index.upsert(
                vectors=[(post_id, vector, {"post_id": post_id, "user_id": user_id})],
                namespace=POSTS_NAMESPACE,
            )
        except Exception as e:
            logger.error(f"Failed to upsert post vector {post_id}: {e}")

    def search_posts(self, query: str, limit: int = 10) -> List[str]:
        try:
            vector = self.embed_text(query, input_type="query")
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

    def upsert_user(self, user_id: str, username: str, bio: str = "") -> None:
        try:
            vector = self.embed_text(f"{username}: {bio}", input_type="passage")
            self.pinecone_index.upsert(
                vectors=[(user_id, vector, {"user_id": user_id})],
                namespace=USERS_NAMESPACE,
            )
        except Exception as e:
            logger.error(f"Failed to upsert user vector {user_id}: {e}")

    def search_users(self, query: str, limit: int = 20) -> List[str]:
        try:
            vector = self.embed_text(query, input_type="query")
            results = self.pinecone_index.query(
                vector=vector,
                top_k=limit,
                namespace=USERS_NAMESPACE,
                include_metadata=False,
            )
            return [match.id for match in results.matches]
        except Exception as e:
            logger.error(f"Failed to search user vectors: {e}")
            return []

    def delete_user_vector(self, user_id: str) -> None:
        try:
            self.pinecone_index.delete(ids=[user_id], namespace=USERS_NAMESPACE)
        except Exception as e:
            logger.error(f"Failed to delete user vector {user_id}: {e}")


embedding_service = EmbeddingService()
