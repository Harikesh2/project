# Decision Log

**Rule:** Every code change must update this file before or in the same commit. No exceptions.

---

## RAG-Based Semantic Search

### 1. Goal

Add semantic search to posts and users. No LLM in the search path — pure vector math.

### 2. Architecture

```
Post created:
  "userX: sunset in Goa" → embed → [0.12, -0.45, ...1024 numbers] → stored in Pinecone

Search "beach vibes":
  1. "beach vibes" → embed → vector
  2. Pinecone cosine similarity → post IDs
  3. DynamoDB BatchGetItem → full posts
  4. User sees results
```

No prompt, no chat, no agent. Embedding model converts text → numbers only.

### 3. Decisions

| # | Decision | Status |
|---|----------|--------|
| D1 | **Embedding model:** `llama-text-embed-v2` (Pinecone Inference), 1024 dimensions, cosine similarity | Locked |
| D2 | **Vector DB:** Pinecone, index `social-posts`. Metadata: `post_id` + `user_id` only — never captions | Locked |
| D3 | **Namespaces:** `posts` (post vectors) and `users` (user vectors) in same index | Locked |
| D4 | **Embed text:** posts → `f"{username}: {caption}"`; users → `f"{username}: {bio}"` | Locked |
| D5 | **Source of truth is DynamoDB.** Pinecone stores IDs only; full posts fetched by ID after retrieval | Locked |
| D6 | **Username at embed time** fetched via `user_service.get_user_by_id()` (Clerk claims can be None) | Locked |
| D7 | **Synchronous embedding** inside request thread (no queues — hobby scale). Wrapped in try/except; failure never breaks creation | Locked |
| D8 | **`updated_at` mechanism:** `from_create` sets `updated_at=now`; `update_post` rewrites it. On edit, also rewrite `GSI3SK = updated_at` so edited posts bubble to top | Locked |
| D9 | **Search page:** existing Users/Posts tabs. Posts tab → RAG. Users tab gets same canonical RAG treatment | Locked |
| D10 | **SDK:** `pinecone` built-in. Env var: `PINECONE_API_KEY`. No OpenAI, no Moonshot | Locked |
| D11 | **No metadata bloat:** no caching, no queues, no hashtag search, no user-vector preview in Pinecone | Locked |
| D12 | **Embedding failures** logged, never fatal. Pinecone failures degrade to DynamoDB fallback | Locked |

### 4. API contract

```
GET /api/search/posts?q={query}&limit=10

Logic:
  if not query:
      return recent_posts_from_dynamodb(limit)      # GSI3 global feed
  else:
      ids = pinecone_query(embed(query))
      if not ids:
          return recent_posts_from_dynamodb(limit)  # zero-result fallback
      return batch_get_dynamodb(ids)                # full posts
```

```
GET /api/search/users?q={query}&limit=20

Logic:
  if not query:
      return recent_users_from_dynamodb(limit)      # bounded Scan
  else:
      ids = pinecone_query(embed(query))
      if not ids:
          return keyword_search_dynamodb(query)     # fallback
      return batch_get_users(ids)
```

### 5. Embedding lifecycle

| Event | Action |
|-------|--------|
| Post created | upsert vector in try/except |
| Post edited | re-embed + rewrite GSI3SK |
| Post deleted | delete vector from Pinecone |
| User created | upsert vector in try/except |
| User updated | re-embed if username/bio changed |
| User deleted | delete vector from Pinecone |

---

## Feed Performance

### 6. Problem

Feed endpoint took 29s to load. Each DynamoDB call opened a new TCP+TLS connection via aioboto3. 50 follows = 101 connections + 151 sequential ops.

### 7. Decisions

| # | Decision | Status |
|---|----------|--------|
| D13 | **Single connection per request.** Feed endpoint opens one `db_connection.get_async_resource()` and passes the table to all sub-queries | Locked |
| D14 | **Batch user lookups.** After collecting all posts, fetch all author users via `batch_get_users()` in one call instead of N calls | Locked |
| D15 | **`get_user_posts_for_feed(table, user_id)`** — lightweight query, no user lookup, takes table as param to share connection | Locked |
| D16 | **`get_global_feed(table, limit)`** — queries GSI3 `GSI3-global-feed-index` for newest posts globally | Locked |

---

## Empty Feed for New Users

### 8. Problem

New users with 0 follows see empty feed `[]`. No global feed fallback existed.

### 9. Decisions

| # | Decision | Status |
|---|----------|--------|
| D17 | **Global feed fallback.** When `following_ids` is empty, feed endpoint returns posts from GSI3 global feed instead of `[]` | Locked |

---

## Search Endpoint Fixes

### 10. Decisions

| # | Decision | Status |
|---|----------|--------|
| D18 | **`get_global_feed(table=None)`** — optional param; opens own connection when None. Search endpoint calls with None (simple), feed endpoint passes shared table | Locked |
| D19 | **Search user lookups** — batch via `batch_get_users()` instead of N+1 `get_user_by_id()` calls | Locked |
| D20 | **Search tests mock Pinecone** — `embedding_service.search_users` patched to `[]` so tests exercise keyword fallback path, not external API | Locked |
| D21 | **Single CI workflow** — `backend-ci.yml` renamed to `ci.yml`; added `frontend` job (Node 18, `npm ci`, `npm run lint`, `npm run build`) running parallel to `backend` job | Locked |

---

## DynamoDB Single-Table Design

### 11. Table: `SocialMedia`

Primary key: `Pk` (HASH), `Sk` (RANGE)

| GSI | Index name | PK | SK | Purpose |
|-----|------------|----|----|---------|
| GSI1 | `GSI1-email-index` | `GSI1PK` | `GSI1SK` | User by email |
| GSI2 | `GSI2-username-index` | `GSI2PK` | `GSI2SK` | User by username |
| GSI3 | `GSI3-global-feed-index` | `GSI3PK=POSTS` | `GSI3SK=created_at` | Global post feed |

### 12. Entity layout

| Entity | PK | SK |
|--------|----|----|
| User metadata | `USER#{user_id}` | `METADATA` |
| User profile | `USER#{user_id}` | `PROFILE` |
| Post metadata | `POST#{post_id}` | `METADATA` |
| User timeline post | `USER#{user_id}` | `POST#{post_id}` |
| Following edge | `USER#{follower_id}` | `FOLLOWING#{target_id}` |
| Follower edge | `USER#{target_id}` | `FOLLOWER#{follower_id}` |
| Post like | `POST#{post_id}` | `LIKE#{user_id}` |
| User like | `USER#{user_id}` | `LIKE#{post_id}` |
| Comment | `POST#{post_id}` | `COMMENT#{comment_id}` |
| User comment | `USER#{user_id}` | `COMMENT#{comment_id}` |

---

## Constraints

- No OpenAI. Only `pinecone` package + `PINECONE_API_KEY`.
- No queues. Embed inside the FastAPI request thread.
- Pinecone metadata = `{post_id, user_id}` only (posts) / `{user_id}` only (users).
- Embedding failures logged, never fatal.
- All API response shapes unchanged from existing endpoints.
- **Every code change must update this file.**
