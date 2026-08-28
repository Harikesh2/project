# Implementation Plan — RAG-Based Feed Search

Execution plan for the decisions in `decision.md`. Each phase builds on the last; phases are independently verifiable.

> **Approach:** One phase at a time — plan, implement, verify, then move to the next phase in a new chat.

---

## Phase 0 — Config & dependencies

**Files:** `backend/requirements.txt`, `backend/app/core/config.py`, `backend/.env.example`

- Add deps: `openai`, `pinecone`.
- Add env vars to `Settings`: `moonshot_api_key`, `pinecone_api_key`, `pinecone_index` (default `social-posts`).
- Document in `.env.example`.

**Verify:** `python -c "import openai, pinecone"` + config loads without error.

**Status:** ✅ Complete

## Phase 1 — Backend RAG (posts)

**Files:** `backend/app/services/embedding_service.py` (new), `backend/app/api/search.py` (new), `backend/app/services/post_service.py`, `backend/app/api/posts.py`, `backend/app/main.py`

1. `embedding_service.py`:
   - `embed_text(text) -> list[float]` (1536-d, via `moonshot-v1-embed` via `openai` SDK).
   - `upsert_post(post_id, user_id, username, caption)` → embed `f"{username}: {caption}"`, upsert namespace `posts`, metadata `{post_id, user_id}`.
   - `search_posts(query, limit) -> list[post_id]` → embed query → Pinecone query → return IDs in score order.
   - `delete_post_vector(post_id)` → `index.delete([post_id])`.
   - Every method `try/except` + logs; never raises into API paths.
2. `api/search.py`: `GET /api/search/posts?q=&limit=10`
   - empty `q` → `post_service.get_global_feed(limit)`
   - else `search_posts()` → if empty → fallback to feed
   - batch-fetch full posts via `post_service.batch_get_posts(ids)` and enrich to `PostWithUser`.
3. `post_service.batch_get_posts(ids)`: `BatchGetItem` (chunk ≤100), reorder results to match input ID order.
4. Hooks in `post_service.py`:
   - **Create:** after save → fetch username via `user_service.get_user_by_id()` → `upsert_post(...)` in `try/except`.
   - **Edit:** `GSI3SK = updated_at` added to update expression + re-embed content in `try/except`.
   - **Delete:** `delete_post_vector(post_id)` in `try/except`.
5. Register `search.router` in `main.py`.

**Verify:** pytest suite green; manual `GET /api/search/posts?q=` and `?q=beach` against local DynamoDB + mocked Pinecone.

**Status:** ✅ Complete

## Phase 2 — User search (same canonical)

**Files:** `backend/app/services/embedding_service.py`, `backend/app/services/user_service.py`

1. `embedding_service`: `upsert_user(user_id, username, bio)` → namespace `users`, metadata `{user_id}` only.
2. `user_service.search_users()`:
   - empty `query` → recent users (bounded Scan `Pk begins_with USER#` AND `Sk=METADATA`, limit).
   - else → embed → Pinecone namespace `users` → batch-get users → fallback to existing keyword Scan.

**Verify:** users tab fast on empty query; semantic matches for typed queries; keyword fallback intact.

**Status:** ✅ Complete

## Phase 3 — Backfill script

**Files:** `scripts/backfill_embeddings.py` (new)

- Iterate posts via `get_global_feed` (GSI3), embed + upsert each.
- Iterate users via bounded scan, embed + upsert each.
- Idempotent (upsert), logs progress + errors.

**Verify:** run against dev DB → Pinecone populated; rerun is safe.

**Status:** ✅ Complete

## Phase 4 — Frontend

**Files:** `frontend/src/components/SearchBar.tsx` (new), `frontend/src/pages/Search.tsx`, `frontend/src/services/postService.ts`

1. `SearchBar.tsx`: controlled input, 300ms debounce.
2. `Search.tsx`: use `SearchBar`; posts tab fires RAG query on mount + on debounce; 3 gray skeleton cards while loading; render via existing `PostCard`.
3. `postService.ts`: repoint `useSearchPosts` → `GET /search/posts?q=&limit=10` (or add `useSemanticSearch`).
4. Users tab: UI unchanged (backend already faster from Phase 2).

**Verify:** `npm run build` passes; `/search` shows recent posts on load, live-updates on typing.

**Status:** ✅ Complete

## Phase 5 — Docs

**Files:** `change.md` (new), `project-changes.md`, `backend/README.md`, `frontend/README.md`

- `change.md`: record every file changed + why (mirrors `project-changes.md` style).
- Update both READMEs with the new endpoint + env vars.
- Append Phase 10 section to `project-changes.md`.

**Status:** ✅ Complete

---

## Ordering rules

- Docs phase last so it reflects reality.
- Each phase ends with a runnable check; no phase ships without its verify step.
- Embedding/vector failures are logged and never fatal — post creation must never depend on Pinecone being up.