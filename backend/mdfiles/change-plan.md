# Change Plan — Pinecone Built-in Embeddings

Migrate from Moonshot AI (OpenAI SDK) embeddings to Pinecone-hosted `llama-text-embed-v2` (1024-dim). Recreate the `social-posts` index.

> **Context:** Moonshot `moonshot-v1-embed` returns 403 — model deprecated. Pinecone Inference API (`pc.inference.embed()`) replaces it with no external dependency.

> **Approach:** Phases 0→3 can run in any order after Phase 0. Phase 4 depends on all prior. Execute sequentially.

---

## Phase 0 — Config & dependencies

**Files:**
- `backend/requirements.txt`
- `backend/app/core/config.py`
- `backend/.env.example`

### Changes

**requirements.txt** — remove `openai>=1.0.0` (line 11). Keep `pinecone>=5.0.0`.

**config.py** — remove `moonshot_api_key: str = ""` (line 34). Keep `pinecone_api_key` and `pinecone_index`.

**.env.example** — remove `MOONSHOT_API_KEY=your_moonshot_api_key` (line 30). Keep `PINECONE_API_KEY` and `PINECONE_INDEX`.

### Verify

```bash
cd backend
python -c "from app.core.config import settings; assert not hasattr(settings, 'moonshot_api_key'); print('ok')"
```

---

## Phase 1 — Rewrite embedding_service.py

**File:** `backend/app/services/embedding_service.py`

### What changes

Replace OpenAI SDK client with Pinecone Inference API. Same public method signatures — callers (post_service, user_service, search.py, backfill) are unaffected.

### New implementation pattern

```python
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
            self._pinecone_index = self.pinecone.index(settings.pinecone_index)
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
```

### Key differences from old code

| Aspect | Old (Moonshot) | New (Pinecone) |
|--------|----------------|----------------|
| Client | `OpenAI(api_key=..., base_url=...)` | `Pinecone(api_key=...)` |
| Embed call | `client.embeddings.create(model=..., input=[...])` | `pc.inference.embed(model=..., inputs=[...], parameters={...})` |
| Response access | `response.data[0].embedding` | `response.data[0]["values"]` |
| input_type | N/A | `"passage"` for indexing, `"query"` for search |
| Dimensions | 1536 | 1024 |

### No changes needed in callers

These files import `embedding_service` but call the same method signatures — no edits required:
- `backend/app/services/post_service.py` (lines 136, 291)
- `backend/app/services/user_service.py` (lines 67, 200, 228, 279)
- `backend/app/api/search.py` (lines 24, 48)
- `backend/scripts/backfill_embeddings.py` (lines 40, 73)

### Verify

```bash
cd backend
python -c "
from app.services.embedding_service import embedding_service
v = embedding_service.embed_text('hello world', input_type='query')
assert len(v) == 1024, f'expected 1024, got {len(v)}'
print(f'embed ok: {len(v)} dims')
"
```

---

## Phase 2 — Recreate Pinecone index

### Action

Delete the old 1536-dim `social-posts` index. Create a new one at 1024 dimensions.

```python
from pinecone import Pinecone, ServerlessSpec
pc = Pinecone(api_key="<YOUR_PINECONE_API_KEY>")

# Delete old index
pc.delete_index("social-posts")

# Create new 1024-dim index
pc.create_index(
    name="social-posts",
    dimension=1024,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)

# Wait until ready
import time
while not pc.describe_index("social-posts").status["ready"]:
    time.sleep(1)
print("index ready")
```

### Verify

```python
desc = pc.describe_index("social-posts")
assert desc.dimension == 1024
print(f"index: {desc.dimension}d, metric: {desc.metric}")
```

---

## Phase 3 — Backfill existing data

**File:** `backend/scripts/backfill_embeddings.py`

### Bug fix

Move `processed += 1` inside the `try` block (lines 41, 74) so failed embeddings aren't counted as processed.

Before:
```python
try:
    embedding_service.upsert_post(post_id, user_id, username, content)
    processed += 1  # ← counts failures too
except Exception as e:
    print(f"  failed post {post_id}: {e}")
    failed += 1
```

After:
```python
try:
    embedding_service.upsert_post(post_id, user_id, username, content)
    processed += 1  # ← only counts successes
except Exception as e:
    print(f"  failed post {post_id}: {e}")
    failed += 1
```

Same fix for `backfill_users` (line 74).

### Run

```bash
cd backend
python scripts/backfill_embeddings.py
```

### Verify

```python
from pinecone import Pinecone
pc = Pinecone(api_key="<KEY>")
index = pc.index("social-posts")
# Check posts namespace
stats = index.describe_namespace_stats(namespace="posts")
print(f"posts vectors: {stats.vector_count}")
# Check users namespace
stats = index.describe_namespace_stats(namespace="users")
print(f"users vectors: {stats.vector_count}")
```

---

## Phase 4 — End-to-end verification

| Test | Expected |
|------|----------|
| `POST /api/posts` with content | Vector upserted to Pinecone `posts` namespace |
| `GET /api/search/posts?q=hello` | Returns results (or empty list, not 500) |
| `PUT /api/posts/{id}` with new content | Vector updated in Pinecone |
| `DELETE /api/posts/{id}` | Vector deleted from Pinecone |
| `POST /api/users` or `PUT /api/users/me` | Vector upserted to Pinecone `users` namespace |
| `GET /api/search/users?q=test` | Returns results (or empty list, not 500) |

---

## Phase summary

| Phase | Files changed | Depends on |
|-------|---------------|------------|
| 0 | `requirements.txt`, `config.py`, `.env.example` | — |
| 1 | `embedding_service.py` | Phase 0 |
| 2 | Pinecone index (infra) | Phase 0 |
| 3 | `backfill_embeddings.py` (bug fix) | Phase 1, 2 |
| 4 | None (verification only) | Phase 3 |
