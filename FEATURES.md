# FEATURES — Feature registry

Status: ✅ Implemented · 🚧 In progress · 📋 Planned

| # | Feature | Endpoint / scope | Status | Phase | Date | Notes |
|---|---------|------------------|--------|-------|------|-------|
| 1 | Clerk auth | All `/api/*` (JWT middleware) | ✅ | — | — | Clerk JWT verification in `backend/app/auth/clerk.py` |
| 2 | User profiles | `/api/users` (+ `/me`) | ✅ | 1, 6 | — | Auto-create from Clerk claims; METADATA + PROFILE items |
| 3 | Posts + timeline | `/api/posts` | ✅ | 2, 8 | — | Canonical POST + USER timeline duplicate; legacy migration |
| 4 | Global feed | `/api/posts/feed` | ✅ | 2 | — | GSI3-global-feed-index |
| 5 | Likes | `/api/posts/{id}/like` | ✅ | 4 | — | Duplicated LIKE items on post + user partitions |
| 6 | Comments | `/api/posts/{id}/comments` | ✅ | 5 | — | Canonical COMMENT item + user activity duplicate |
| 7 | Follows | `/api/users/{id}/follow` | ✅ | 3 | — | Duplicated FOLLOWING/FOLLOWER edges, no GSI |
| 8 | Search | `/api/users/search`, `/api/posts/search` | ✅ | 7 | — | Scan + `Pk`/`Sk` filters |
| 9 | S3 image/avatar upload | `/api/upload-image`, `/api/users/me/avatar` | ✅ | 9 | — | Keys scoped `uploads/{user_id}/…` |
| 10 | Chat | `/api/chat/*`, WebSocket | ✅ | — | — | WebSocket + connection manager |
| 11 | Notifications | `/api/notifications`, WebSocket | ✅ | — | — | WebSocket push |

## Implemented features (detailed)

### Users
- Auto-creates a minimal `USER#{id}/METADATA` + `PROFILE` from Clerk JWT claims on first access.
- Profile fields set via `POST /api/users`, deprecated `POST /api/users/me`, or `PUT /api/users/me`.
- Lookup by email / username via GSI1 / GSI2 (keys lowercased).

### Posts
- Canonical `POST#{id}/METADATA` + timeline duplicate `USER#{id}/POST#{id}` (dual-write).
- Global feed via GSI3; legacy timeline-only posts lazily migrated to canonical form on first read.

### Social graph
- Follows/likes/comments use `attribute_not_exists(Sk)` conditional writes and duplicate items on both partitions — no cross-partition scans for follower/like listings.

### Uploads
- S3 keys scoped per user (`uploads/{user_id}/{uuid}.{ext}`); response `{ message, url, key }`.

### Chat & notifications
- WebSocket-based real-time chat and notification push.
