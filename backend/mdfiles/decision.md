# Decision Log — RAG-Based Feed Search

This document records the locked-in decisions for the RAG-based feed search feature. It is the source of truth the implementing model (and any reviewer) verifies against before touching code.

---

## 1. Goal

Add **semantic feed search** to the social media app. Differentiator: uses **Moonshot AI** (not OpenAI) to showcase vendor-agnostic AI engineering.

The result on the Search page: type a phrase like "beach vibes" and get posts whose *meaning* matches — not just keyword matches.

## 2. How it works — NO LLM in the search path

There is **no prompt, no chat, no agent** anywhere in this feature. RAG here is pure vector math.

The only Moonshot call is the **embedding model** (`moonshot-v1-embed`) — a text→numbers encoder, not a chatbot. Our API key never generates prose.

```
At post creation:
  "userX: sunset in Goa" → embed → [0.12, -0.45, ...1536 numbers] → stored in Pinecone

When someone searches "beach vibes":
  1. "beach vibes" → embed → [0.03, ...1536 numbers]     <- the ONLY AI call
  2. Pinecone compares those numbers to all post vectors (cosine similarity)
  3. Returns closest post_ids (e.g. ["abc", "def"])
  4. We fetch the real posts from DynamoDB by those IDs
  5. User sees results
```

The "AI" part is steps 1–2 — vector math, not generation. **We write zero prompts.** Moonshot never reads a caption again and never answers anything; it only converts words ↔ numbers.

This is why the feature is fast (hobby scale) and why the fallback exists: if Pinecone returns nothing, we return recent posts instead. No dead ends.

## 3. Locked architecture decisions

| # | Decision |
|---|----------|
| D1 | **Embedding model:** `moonshot-v1-embed`, 1536 dimensions, cosine similarity. |
| D2 | **Vector DB:** Pinecone, index `social-posts`. Metadata stored: `post_id` + `user_id` **only** — never captions. |
| D3 | **Namespaces:** `posts` (post vectors) and `users` (user vectors) in the same index. |
| D4 | **Embed text:** posts → `f"{username}: {caption}"`; users → `f"{username}: {bio}"`. |
| D5 | **Source of truth is DynamoDB.** Pinecone stores IDs only; full posts are fetched by ID after retrieval. |
| D6 | **Username at embed time** is fetched via `user_service.get_user_by_id()` (Clerk claims can be `None`). |
| D7 | **Synchronous embedding** on post create, inside the request thread (no queues — hobby scale). Wrapped in `try/except`; embedding failure never breaks post creation. |
| D8 | **`updated_at` mechanism (already in code):** `from_create` sets `updated_at=now`; `update_post` rewrites it. On edit we also rewrite `GSI3SK = updated_at` on the canonical item so edited posts bubble to the top of the recent feed — "fetch by updated_at" with zero index/schema change. |
| D9 | **Search page:** keep existing Users/Posts tabs. Posts tab → RAG. Users tab gets the same canonical RAG treatment (fixes the slow `contains` Scan). |
| D10 | **SDK:** `moonshot` Python package. API key from env `MOONSHOT_API_KEY`. No OpenAI. |
| D11 | **No metadata bloat:** no caching, no queues, no hashtag search, no user-vector preview in Pinecone. |

## 4. API contract (Phase 1)

```
GET /api/search/posts?q={query}&limit=10

Logic:
  if not query:
      return recent_posts_from_dynamodb(limit)      # GSI3 global feed (by updated_at)
  else:
      ids = pinecone_query(embed(query))
      if not ids:
          return recent_posts_from_dynamodb(limit)  # zero-result fallback
      return batch_get_dynamodb(ids)                # full posts, reordered by score
```

Any embedding/Pinecone error degrades to the same fallback (log + recent posts).

## 5. User search (Phase 2 — same canonical approach)

| Query | Behavior |
|-------|----------|
| Empty | **Recent users showcase** — bounded Scan `Pk begins_with USER#` AND `Sk = METADATA`, limit 20 (no GSI for latest users; scan is fine at hobby scale). |
| Text | Embed → Pinecone namespace `users` → batch-get users → fallback to existing keyword Scan. |

## 6. Embedding lifecycle

| Event | Action |
|-------|--------|
| Post created | upsert vector (`f"{username}: {content}"`) in `try/except` |
| Post edited | re-embed (content changed) + rewrite `updated_at` and `GSI3SK` |
| Post deleted | `index.delete([post_id])` |
| Backfill | `scripts/backfill_embeddings.py` embeds all existing posts + users |

## 7. Frontend

- `SearchBar.tsx` with 300ms debounce.
- 3 gray skeleton cards while loading.
- Posts tab reuses existing `PostCard` / `PostWithUser` shape.
- Route `/search` already exists (App.tsx).

## 8. Constraints for the coder

- No OpenAI anywhere. Only `moonshot` package + `MOONSHOT_API_KEY`.
- No queues. Embed inside the FastAPI request thread.
- Pinecone metadata = `{post_id, user_id}` only (posts) / `{user_id}` only (users).
- Embedding failures are logged, never fatal.
- All API response shapes unchanged from existing endpoints.