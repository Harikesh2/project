# Project Changes — Single-Table DynamoDB Refactor

This document tracks the migration from simple primary-key tables to a **Single Table Design** on the `SocialMedia` DynamoDB table using composite keys (`Pk`, `Sk`) and GSIs.

---

## Phase 1: User Model (`backend/app/models/user.py`)

**Status:** Complete

### What changed

The user model layer was split into **DynamoDB persistence models** and **API contract models**. The public REST API shape is unchanged so frontend clients continue to work without modification.

### DynamoDB entity layout

| Item | PK | SK | Purpose |
|------|----|----|---------|
| User metadata | `USER#{user_id}` | `METADATA` | Canonical user record (username, email, counters) |
| User profile | `USER#{user_id}` | `PROFILE` | Display fields (`avatar_url`, `bio`) |

### GSI attributes on METADATA items

| GSI | Index name | Partition key | Sort key | Access pattern |
|-----|------------|---------------|----------|----------------|
| GSI1 | `GSI1-email-index` | `GSI1PK` = `EMAIL#{email}` | `GSI1SK` = `USER` | Lookup user by email |
| GSI2 | `GSI2-username-index` | `GSI2PK` = `USERNAME#{username}` | `GSI2SK` = `USER` | Lookup user by username |

Email and username GSI keys are stored **lowercased** for case-insensitive lookups.

### New Python types

| Type | Role |
|------|------|
| `UserEntityKeys` | Static helpers for PK/SK and GSI key construction |
| `UserMetadataRecord` | DynamoDB item at `SK=METADATA` |
| `UserProfileItem` | DynamoDB item at `SK=PROFILE` |
| `merge_user_records()` | Combines METADATA + PROFILE into API `User` |
| `UserSearch.from_user()` | Maps API `User` → `UserSearch` |

### Unchanged API models

These remain the HTTP contract (request/response bodies):

- `UserBase`, `UserCreate`, `UserUpdate`
- `User` (full profile response)
- `UserProfile` (`User` + `is_following` / `is_followed_by`)
- `UserSearch` (lightweight user card)

---

## Files updated in Phase 1

### Backend

| File | Changes |
|------|---------|
| `backend/app/models/user.py` | Single-table key helpers, DynamoDB item models, merge utilities |
| `backend/app/services/user_service.py` | Writes/reads METADATA + PROFILE; GSI1/GSI2 queries; `get_user_by_email()` added |
| `backend/app/database/setup.py` | Replaced multi-table setup with single `SocialMedia` table (`Pk`/`Sk` + 3 GSIs) |
| `backend/app/api/users.py` | Uses `UserSearch.from_user()` helper |
| `backend/tests/conftest.py` | Single-table create/clear lifecycle |
| `backend/tests/test_users.py` | Fixed follow endpoint assertion (`following` + `success`) |

### Frontend

| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | Added comments documenting DynamoDB key mapping (no API shape changes) |

No frontend service or component changes were required — the REST API contract is identical.

---

## Table definition (`SocialMedia`)

```
Primary key:  Pk (HASH), Sk (RANGE)

GSI1-email-index:     GSI1PK (HASH), GSI1SK (RANGE)
GSI2-username-index:  GSI2PK (HASH), GSI2SK (RANGE)
GSI3-global-feed-index: GSI3PK (HASH), GSI3SK (RANGE)  — global post feed (Phase 2)
```

Run table creation:

```bash
cd backend
python -m app.database.setup
```

---

## User service access patterns

| Operation | DynamoDB API | Key / Index |
|-----------|--------------|-------------|
| Get user by ID | `GetItem` × 2 | `USER#{id}` / `METADATA` + `PROFILE` |
| Get user by email | `Query` | `GSI1-email-index` |
| Get user by username | `Query` | `GSI2-username-index` |
| Create user | `PutItem` × 2 | METADATA (conditional) + PROFILE |
| Update user | `UpdateItem` | METADATA (+ GSI2 keys if username changes), PROFILE if avatar/bio |
| Delete user | `DeleteItem` × 2 | METADATA + PROFILE |
| Search users | `Scan` + filter | `Sk=METADATA` and `username contains query` (no GSI for partial match) |
| Increment counters | `UpdateItem` | METADATA only |

---

## Phase 2: Post Model (`backend/app/models/post.py`)

**Status:** Complete

### What changed

Posts now use a **canonical METADATA item** plus a **timeline duplicate** under the author's user partition. The REST API shape is unchanged.

### DynamoDB entity layout

| Item | PK | SK | Purpose |
|------|----|----|---------|
| Canonical post | `POST#{post_id}` | `METADATA` | Source of truth for post data |
| User timeline entry | `USER#{user_id}` | `POST#{post_id}` | Query a user's posts without a GSI |

### GSI attributes on METADATA items

| GSI | Index name | Partition key | Sort key | Access pattern |
|-----|------------|---------------|----------|----------------|
| GSI3 | `GSI3-global-feed-index` | `GSI3PK` = `POSTS` | `GSI3SK` = `created_at` | Newest posts globally |

### New Python types

| Type | Role |
|------|------|
| `PostEntityKeys` | PK/SK and GSI3 key builders |
| `PostMetadataRecord` | DynamoDB item at `POST#{id}/METADATA` |
| `UserTimelinePostRecord` | Timeline duplicate at `USER#{user_id}/POST#{post_id}` |
| `record_to_post()` | Maps DynamoDB item → API `Post` |
| `PostWithUser.from_post_and_user()` | Builds enriched post response |

### Unchanged API models

- `PostBase`, `PostCreate`, `PostUpdate`
- `Post`, `PostWithUser`

### Post service access patterns

| Operation | DynamoDB API | Key / Index |
|-----------|--------------|-------------|
| Get post by ID | `GetItem` | `POST#{id}` / `METADATA` |
| Get user posts | `Query` | `USER#{id}`, `SK begins_with POST#` |
| Global feed | `Query` | `GSI3-global-feed-index` |
| Create post | `PutItem` × 2 | METADATA (conditional) + timeline duplicate |
| Update post | `UpdateItem` × 2 | METADATA + timeline |
| Delete post | `DeleteItem` × 2 | METADATA + timeline |
| Search posts | `Scan` + filter | `Sk=METADATA` and `content contains query` |
| Increment likes/comments | `UpdateItem` × 2 | METADATA + timeline |

### Files updated in Phase 2

| File | Changes |
|------|---------|
| `backend/app/models/post.py` | Key helpers, DynamoDB item models, merge utilities |
| `backend/app/services/post_service.py` | Dual-write/read pattern, GSI3 global feed method, canonical lookups |
| `backend/app/api/posts.py` | Uses `PostWithUser.from_post_and_user()` |
| `frontend/src/types/index.ts` | DynamoDB key mapping comments for posts |

---

## Phase 3: Follow Model (`backend/app/models/follow.py`)

**Status:** Complete

### What changed

Follow relationships are stored as **duplicated edge items** with distinct sort-key prefixes, enabling follower and following queries without a GSI.

### DynamoDB entity layout

| Item | PK | SK | Purpose |
|------|----|----|---------|
| Following edge | `USER#{follower_id}` | `FOLLOWING#{target_user_id}` | Who this user follows |
| Follower edge | `USER#{target_user_id}` | `FOLLOWER#{follower_id}` | Who follows this user |

### New Python types

| Type | Role |
|------|------|
| `FollowEntityKeys` | PK/SK builders for `FOLLOWING#` / `FOLLOWER#` prefixes |
| `FollowingRecord` | Following-list edge item |
| `FollowerRecord` | Followers-list edge item |
| `record_to_follow()` | Maps DynamoDB item → API `Follow` |
| `FollowWithUser.from_follow_and_user()` | Builds enriched follow response |

### Unchanged API models

- `Follow`, `FollowWithUser`

### Follow service access patterns

| Operation | DynamoDB API | Key / Index |
|-----------|--------------|-------------|
| Follow user | `PutItem` × 2 | FOLLOWING edge (conditional) + FOLLOWER edge |
| Unfollow user | `DeleteItem` × 2 | Both edges |
| Is following | `GetItem` | `USER#{follower}/FOLLOWING#{target}` |
| Get followers | `Query` | `USER#{id}`, `SK begins_with FOLLOWER#` |
| Get following | `Query` | `USER#{id}`, `SK begins_with FOLLOWING#` |
| Get following IDs | `Query` | Same as following (projection on `following_id`) |

### Bug fix

Follow creation now uses `attribute_not_exists(Sk)` instead of `attribute_not_exists(Pk)`, so follows work when the user partition already contains `METADATA` / `PROFILE` items.

### Files updated in Phase 3

| File | Changes |
|------|---------|
| `backend/app/models/follow.py` | Key helpers, duplicated edge item models |
| `backend/app/services/follow_service.py` | Dual-write edges, partition queries (no GSI) |
| `frontend/src/types/index.ts` | DynamoDB key mapping comments for follows |

---

## Phase 4: Like Model (`backend/app/models/like.py`)

**Status:** Complete

### What changed

Likes are stored as **duplicated relationship items** on the post and user partitions. The like toggle API response is unchanged.

### DynamoDB entity layout

| Item | PK | SK | Purpose |
|------|----|----|---------|
| Like on post | `POST#{post_id}` | `LIKE#{user_id}` | Who liked a post |
| Liked by user | `USER#{user_id}` | `LIKE#{post_id}` | Posts liked by a user |

### New Python types

| Type | Role |
|------|------|
| `LikeEntityKeys` | PK/SK builders for `LIKE#` prefix |
| `PostLikeRecord` | Like item on post partition |
| `UserLikeRecord` | Like item on user partition |
| `record_to_like()` | Maps DynamoDB item → API `Like` |

### Like service access patterns

| Operation | DynamoDB API | Key / Index |
|-----------|--------------|-------------|
| Like post | `PutItem` × 2 | POST like (conditional) + USER like |
| Unlike post | `DeleteItem` × 2 | Both like items |
| Is liked | `GetItem` | `POST#{id}/LIKE#{user_id}` |
| Get liked post IDs | `Query` | `USER#{id}`, `SK begins_with LIKE#` |

### Bug fix

Like creation uses `attribute_not_exists(Sk)` so likes work when the post partition already has `METADATA` or `COMMENT#` items.

### Files updated in Phase 4

| File | Changes |
|------|---------|
| `backend/app/models/like.py` | Key helpers, duplicated like item models |
| `backend/app/services/like_service.py` | Dual-write likes, partition queries |

---

## Phase 5: Comment Model (`backend/app/models/comment.py`)

**Status:** Complete

### What changed

Comments use a **canonical item** under the post partition plus an optional **user activity duplicate**. The REST API shape is unchanged.

### DynamoDB entity layout

| Item | PK | SK | Purpose |
|------|----|----|---------|
| Canonical comment | `POST#{post_id}` | `COMMENT#{comment_id}` | Comments on a post |
| User activity | `USER#{user_id}` | `COMMENT#{comment_id}` | User comment history |

### New Python types

| Type | Role |
|------|------|
| `CommentEntityKeys` | PK/SK builders for `COMMENT#` prefix |
| `PostCommentRecord` | Canonical comment on post partition |
| `UserCommentRecord` | User activity duplicate |
| `record_to_comment()` | Maps DynamoDB item → API `Comment` |
| `CommentWithUser.from_comment_and_user()` | Builds enriched comment response |

### Unchanged API models

- `CommentBase`, `CommentCreate`, `CommentUpdate`
- `Comment`, `CommentWithUser`

### Comment service access patterns

| Operation | DynamoDB API | Key / Index |
|-----------|--------------|-------------|
| Create comment | `PutItem` × 2 | POST comment (conditional) + USER duplicate |
| Get post comments | `Query` | `POST#{id}`, `SK begins_with COMMENT#` |
| Delete comment | `DeleteItem` × 2 | POST comment + USER duplicate |

### Files updated in Phase 5

| File | Changes |
|------|---------|
| `backend/app/models/comment.py` | Key helpers, DynamoDB item models, merge utilities |
| `backend/app/services/comment_service.py` | Dual-write comments, partition queries |
| `frontend/src/types/index.ts` | DynamoDB key mapping comments for comments |

---

## Phase 6: Test & API Fixes (single-table compatibility)

**Status:** Complete

### Root causes

| Failure | Cause | Fix |
|---------|-------|-----|
| `test_create_and_get_user_profile` | `GET /api/users/me` auto-creates `METADATA` + `PROFILE` from Clerk claims; test expected `404` | Test updated: assert auto-create, then `PUT /me` for profile fields |
| `test_create_profile_deprecated_endpoint` | Same auto-create assumption; `POST /api/users/me` was missing | Added deprecated `POST /me` route; test creates via alias directly |
| `test_create_profile_deprecated_endpoint_uses_same_conflict_behavior` | `POST /api/users/me` returned `405` | Deprecated route added; shares `_create_authenticated_user_profile()` |
| `test_create_user_profile_already_exists` | `POST /api/users` did not catch `ValueError` → `500` instead of `400` | `create_user` now delegates to `_create_authenticated_user_profile()` |
| `test_create_user_openapi_marks_only_me_alias_deprecated` | No `POST` on `/api/users/me` in OpenAPI | Deprecated `POST /me` endpoint registered |
| `test_upload_image_success` | `s3_service.upload_file()` now receives `user_id` | Mock assertion updated with `user_id="test_user_123"` |

### Backend fixes

| File | Change |
|------|--------|
| `backend/app/services/user_service.py` | `create_user` uses `attribute_not_exists(Sk)` on METADATA (correct for shared `USER#` partitions) |
| `backend/app/api/users.py` | `POST /api/users` uses `_create_authenticated_user_profile()`; added deprecated `POST /api/users/me` |

### Test updates

| File | Change |
|------|--------|
| `backend/tests/test_users.py` | Auto-create flow, `asyncio.run()` for follow test, deprecated endpoint tests |
| `backend/tests/test_upload.py` | S3 mock includes `user_id` parameter |

### Single-table user creation condition

On a composite-key table, `attribute_not_exists(Pk)` fails when **any** item shares the partition key (e.g. `PROFILE` already exists). User METADATA creation now uses:

```text
ConditionExpression = attribute_not_exists(Sk)
```

This checks only the specific `USER#{id}/METADATA` item, matching the pattern used for likes, comments, and follows.

---

## Testing

Requires DynamoDB Local on `http://localhost:8001` (default in `conftest.py`).

```bash
cd backend
python -m pytest tests/ -v
```

---

## Migration notes

- **Existing data** in old per-entity tables is not auto-migrated. Recreate the `SocialMedia` table and re-seed for local dev.
- **Test isolation**: `conftest.py` clears all items from `SocialMedia` before each test.
- **API compatibility**: All endpoints return the same JSON fields as before. Frontend requires no service or component changes.
- **GET /api/users/me** auto-creates a minimal user from Clerk JWT claims on first access; explicit profile fields are set via `POST /api/users`, `POST /api/users/me` (deprecated), or `PUT /api/users/me`.

---

## Phase 7: Search fixes (single-table Scan filters)

**Status:** Complete

### Root cause

`search_users` and `search_posts` filtered only on `Sk = METADATA`. In the single-table design, **both** users (`USER#{id}/METADATA`) and posts (`POST#{id}/METADATA`) share the same sort key, so scans returned post items when parsing user results — causing `ValidationError` (missing `GSI1PK` / `GSI2PK`).

Legacy user rows created before GSI attributes were added could also fail validation on read.

### Fixes

| File | Change |
|------|--------|
| `backend/app/services/user_service.py` | Scan filter adds `Pk begins_with USER#`; hydrates via `get_user_by_id()` |
| `backend/app/services/post_service.py` | Scan filter adds `Pk begins_with POST#` |
| `backend/app/models/user.py` | `UserMetadataRecord.from_dynamo_item()` backfills GSI keys from `email` / `username` when absent |
| `backend/app/models/user.py` | Added `USER_PK_PREFIX` constant |
| `backend/app/models/post.py` | Added `POST_PK_PREFIX` constant |

### Correct Scan filters

```text
Users: Pk begins_with USER#  AND Sk = METADATA  AND username contains :q
Posts: Pk begins_with POST#  AND Sk = METADATA  AND content contains :q
       OR Pk begins_with USER#  AND Sk begins_with POST#  AND content contains :q  (legacy)
```

---

## Phase 8: Legacy post compatibility (timeline-only items)

**Status:** Complete

### Root cause

Posts created **before** the single-table refactor were stored only as:

```text
PK = USER#{user_id}
SK = POST#{post_id}
```

They had **no** canonical `POST#{post_id}/METADATA` item. After migration, these operations broke:

| Operation | Why it failed |
|-----------|----------------|
| Get post by ID | `get_post_by_id` only read `POST#/METADATA` |
| Edit post | Could not resolve post; update targeted missing METADATA key |
| Search | Scan filtered `POST#/METADATA` only |
| Like / unlike | `increment_likes_count` called `get_post_by_id` → no-op |
| Comments | API checks `get_post_by_id` before create → `404 Post not found` |

Feed and user timelines still worked because they query `USER#/POST#*` directly.

### Fixes

| File | Change |
|------|--------|
| `backend/app/services/post_service.py` | `_get_raw_post_item()` — canonical METADATA, then legacy timeline fallback via `Sk = POST#{id}` |
| `backend/app/services/post_service.py` | `_ensure_canonical_post()` — lazy migration writes `POST#/METADATA` from timeline data |
| `backend/app/services/post_service.py` | `_get_existing_post_keys()` / `_update_all_post_items()` — update only keys that exist |
| `backend/app/services/post_service.py` | `search_posts` includes `USER#/POST#*` legacy items; dedupes by `post_id` |
| `backend/app/models/post.py` | `PostMetadataRecord.from_timeline_item()`, `is_legacy_timeline_post()` |
| `backend/tests/test_posts.py` | `test_legacy_timeline_post_edit_search_like_comments` |

### Lazy migration

On first read, like, comment, or edit of a legacy post, the service writes a canonical `POST#{id}/METADATA` item (with GSI3 keys backfilled from `created_at`). The original timeline item is preserved. Subsequent operations update **both** representations when present.

### Resolution order

```text
1. GetItem  POST#{post_id} / METADATA
2. Scan      Sk = POST#{post_id} AND Pk begins_with USER#  (legacy timeline item, paginated)
3. Optional  PutItem POST#/METADATA  (lazy migration)
```

---

## Phase 8b: Legacy post scan pagination fix

**Status:** Complete

### Root cause

Phase 8 introduced legacy lookup via `table.scan(FilterExpression=Sk = POST#{id}, Limit=1)`. In DynamoDB, **`Limit` applies to items evaluated before the filter**, not matching results returned. After user creation the table already contains `USER#/METADATA` and `USER#/PROFILE` items; a single-page scan with `Limit=1` often evaluated those rows first, filtered them out, and returned **zero matches** — causing `404 Post not found` for legacy posts even though the timeline item existed.

The same pre-filter limit issue affected `search_posts`, which used `Limit=limit * 2`.

### Symptom

| Test / operation | Failure |
|------------------|---------|
| `test_legacy_timeline_post_edit_search_like_comments` | `GET /api/posts/{id}` → `404` after seeding legacy `USER#/POST#{id}` item |
| Search legacy posts | Legacy timeline items missed when table had other user items |
| Like / comment / edit / delete on legacy posts | All blocked because `get_post_by_id` returned `None` |

### Fixes

| File | Change |
|------|--------|
| `backend/app/services/post_service.py` | Added `_find_legacy_timeline_item()` — paginated scan with `Sk = POST#{id}` AND `Pk begins_with USER#` |
| `backend/app/services/post_service.py` | `_get_raw_post_item()` delegates legacy fallback to `_find_legacy_timeline_item()` (removed `Limit=1`) |
| `backend/app/services/post_service.py` | `search_posts()` paginates until enough results or table exhausted (removed `Limit=limit * 2`) |
| `backend/tests/test_posts.py` | `test_legacy_timeline_post_edit_search_like_comments` extended with delete assertion |

### Correct legacy scan pattern

```text
Filter:  Sk = POST#{post_id}  AND  Pk begins_with USER#
Paginate: loop scan pages via LastEvaluatedKey until match or exhausted
Never:   use Scan Limit=1 expecting a filter hit
```

Edit, like, comment, and delete on legacy posts continue to use the Phase 8 lazy-migration and dual-write paths once the post resolves.

---

## Phase 9: Upload & image upload platform fixes

**Status:** Complete

### Root causes

| Failure | Cause | Fix |
|---------|-------|-----|
| `test_upload_image_success` | `s3_service.upload_file()` now receives `user_id` | Mock assertion updated with `user_id="test_user_123"` |
| Post / image upload broken in browser | Frontend set `Content-Type: multipart/form-data` manually, stripping the multipart **boundary** | Removed manual header; let axios set boundary |
| Avatar upload 404 | `POST /api/users/me/avatar` called `update_user` before user record existed | Auto-create user via `_auto_create_user_from_claims()` when missing |
| Avatar S3 path flat | Avatar endpoint did not pass `user_id` to `s3_service.upload_file()` | Pass `user_id` so keys land under `uploads/{user_id}/...` |
| Type mismatch | Frontend `UploadResponse` expected `{ filename, content_type, size }` | Aligned to backend `{ message, url, key }` |

### Backend fixes

| File | Change |
|------|--------|
| `backend/app/api/upload.py` | Passes `user_id=current_user["user_id"]` to `s3_service.upload_file()` |
| `backend/app/api/users.py` | Avatar upload passes `user_id` to S3; auto-creates user if not found; closes upload file in `finally` |

### Frontend fixes

| File | Change |
|------|--------|
| `frontend/src/services/uploadService.ts` | `UploadResponse` matches backend; clears default JSON `Content-Type` for FormData |
| `frontend/src/services/userService.ts` | Avatar upload no longer sets manual `multipart/form-data` header |
| `frontend/src/services/api.ts` | Request interceptor deletes `Content-Type` when body is `FormData` (axios sets boundary) |

### Test updates

| File | Change |
|------|--------|
| `backend/tests/test_upload.py` | S3 mock includes `user_id` parameter on `test_upload_image_success` |
| `backend/tests/test_upload.py` | Added `test_upload_avatar_success` (auto-create user + profile update) |

### Upload API contract (unchanged response shape)

```json
{
  "message": "Upload successful",
  "url": "https://{bucket}.s3.{region}.amazonaws.com/uploads/{user_id}/{uuid}.{ext}",
  "key": "uploads/{user_id}/{uuid}.{ext}"
}
```

S3 keys are scoped per user when `user_id` is provided to `s3_service.upload_file()`.

---

## Phase 10: RAG-Based Feed Search

**Status:** Complete

### What changed

Added **semantic search** to posts and users using Moonshot AI embeddings (`moonshot-v1-embed`, 1536-dim) and Pinecone vector storage. No LLM in the search path — pure vector similarity via cosine distance.

### Architecture

```
Post created:
  "userX: sunset in Goa" → embed → [0.12, -0.45, ...1536 numbers] → stored in Pinecone

Search "beach vibes":
  1. "beach vibes" → embed → vector          (Moonshot API call)
  2. Pinecone cosine similarity → post IDs   (vector DB query)
  3. DynamoDB BatchGetItem → full posts      (source of truth)
  4. User sees results
```

### Embedding service (`backend/app/services/embedding_service.py`)

| Function | Namespace | Input | Returns |
|----------|-----------|-------|---------|
| `embed_text(text)` | — | text | `List[float]` (1536-d) |
| `upsert_post(post_id, user_id, username, caption)` | `posts` | post data | None |
| `search_posts(query, limit)` | `posts` | search text | `List[str]` (post IDs) |
| `delete_post_vector(post_id)` | `posts` | post ID | None |
| `upsert_user(user_id, username, bio)` | `users` | user data | None |
| `search_users(query, limit)` | `users` | search text | `List[str]` (user IDs) |
| `delete_user_vector(user_id)` | `users` | user ID | None |

All methods wrapped in `try/except` — embedding failures log and never raise.

### Search API

| Endpoint | Query | Behavior |
|----------|-------|----------|
| `GET /api/search/posts?q=&limit=10` | Empty | Recent posts via GSI3 global feed |
| | Text | Embed → Pinecone → batch-fetch DynamoDB |
| `GET /api/search/users?q=&limit=20` | Empty | Recent users via bounded Scan |
| | Text | Embed → Pinecone → batch-fetch DynamoDB → fallback to keyword Scan |

Both require Clerk auth. Pinecone failures degrade to DynamoDB fallback.

### Embedding lifecycle

| Event | Action |
|-------|--------|
| Post created | `upsert_post()` in `try/except` after DynamoDB save |
| Post edited | Re-embed content + rewrite `GSI3SK = updated_at` |
| Post deleted | `delete_post_vector()` |
| User created | `upsert_user()` in `try/except` |
| User updated | Re-embed if username or bio changed |
| User deleted | `delete_user_vector()` |

### Config additions

| Env var | Purpose |
|---------|---------|
| `MOONSHOT_API_KEY` | Moonshot AI API key for embeddings |
| `PINECONE_API_KEY` | Pinecone vector DB API key |
| `PINECONE_INDEX` | Pinecone index name (default: `social-posts`) |

### Files updated

| File | Changes |
|------|---------|
| `backend/requirements.txt` | Added `openai>=1.0.0`, `pinecone>=5.0.0` |
| `backend/app/core/config.py` | Added `moonshot_api_key`, `pinecone_api_key`, `pinecone_index` |
| `backend/.env.example` | Added RAG env vars |
| `backend/app/services/embedding_service.py` | New — embedding + vector operations |
| `backend/app/api/search.py` | New — search endpoints for posts and users |
| `backend/app/services/post_service.py` | Added `batch_get_posts()`, embedding hooks |
| `backend/app/services/user_service.py` | Added Pinecone-first `search_users()`, embedding hooks |
| `backend/app/main.py` | Registered search router |
| `backend/scripts/backfill_embeddings.py` | New — idempotent backfill script |
| `frontend/src/services/postService.ts` | `useSearchPosts` hits `/api/search/posts` |
| `frontend/src/pages/Search.tsx` | Uses search API endpoints |
