# Change Log — RAG-Based Feed Search

Every file touched across Phases 0–4, what changed and why.

---

## Phase 0 — Config & dependencies

| File | Change |
|------|--------|
| `backend/requirements.txt` | Added `openai>=1.0.0` and `pinecone>=5.0.0` |
| `backend/app/core/config.py` | Added `moonshot_api_key`, `pinecone_api_key`, `pinecone_index` to `Settings` |
| `backend/.env.example` | Added `MOONSHOT_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX` |

---

## Phase 1 — Backend RAG (posts)

| File | Change |
|------|--------|
| `backend/app/services/embedding_service.py` | New — Moonshot embedding + Pinecone vector operations (`embed_text`, `upsert_post`, `search_posts`, `delete_post_vector`) |
| `backend/app/api/search.py` | New — `GET /api/search/posts` endpoint (Pinecone-first with DynamoDB fallback) |
| `backend/app/services/post_service.py` | Added `batch_get_posts()` for multi-ID DynamoDB fetch; added embedding hooks on create/edit/delete |
| `backend/app/main.py` | Registered `search.router` at `/api/search` |

---

## Phase 2 — User search (same canonical)

| File | Change |
|------|--------|
| `backend/app/services/embedding_service.py` | Added `upsert_user()`, `search_users()`, `delete_user_vector()` for `users` namespace |
| `backend/app/services/user_service.py` | `search_users()` — Pinecone-first with keyword Scan fallback; embedding hooks on create/update/delete |
| `backend/app/api/search.py` | Added `GET /api/search/users` endpoint |

---

## Phase 3 — Backfill script

| File | Change |
|------|--------|
| `backend/scripts/backfill_embeddings.py` | New — iterates all posts and users, embeds + upserts to Pinecone (idempotent) |

---

## Phase 4 — Frontend

| File | Change |
|------|--------|
| `frontend/src/services/postService.ts` | `useSearchPosts` now hits `GET /api/search/posts?q=&limit=20` |
| `frontend/src/pages/Search.tsx` | Uses `useSearchPosts` + `useSearchUsers` from `/api/search/*` endpoints |

---

## Summary

| Category | Files changed | Files created |
|----------|---------------|---------------|
| Config | 3 | 0 |
| Backend | 4 | 2 |
| Frontend | 2 | 0 |
| **Total** | **9** | **2** |
