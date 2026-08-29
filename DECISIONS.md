# DECISIONS — Social Media App

> Append only; never delete. Follow D-XX numbering.

| ID | Date | Decision | Why | Status |
|----|------|----------|-----|--------|
| D-01 | 2026-08 | Single-table DynamoDB design: `Pk`/`Sk` composite keys + 3 GSIs on one `SocialMedia` table | Replace per-entity tables with a scalable single-table design; query without joins | Active |
| D-02 | 2026-08 | Email/username GSI keys stored lowercased (`EMAIL#…`, `USERNAME#…`) | Case-insensitive lookups by email / username | Active |
| D-03 | 2026-08 | Follows/likes/comments stored as duplicated edge items on both partitions (`FOLLOWING#`, `FOLLOWER#`, `LIKE#`, `COMMENT#`) | Query a user's followers/following/likes without a GSI or cross-partition scan | Active |
| D-04 | 2026-08 | User METADATA (and like/comment/follow) creation uses `attribute_not_exists(Sk)` | On a composite-key table, `attribute_not_exists(Pk)` fails when any item shares the partition key (e.g. `PROFILE` already exists) | Active |
| D-05 | 2026-08 | Legacy timeline-only posts lazily migrated to canonical `POST#/METADATA` on first read | Pre-refactor posts had no canonical item; edit/like/comment/search would 404 without migration | Active |
| D-06 | 2026-08 | Legacy post lookup and search use paginated scans — never `Scan Limit=1` with a filter | DynamoDB applies `Limit` before filtering, so filtered scans can return zero matches even when data exists | Active |
| D-07 | 2026-08 | S3 object keys scoped per user (`uploads/{user_id}/{uuid}.{ext}`) | Organize uploads by user; pass `user_id` through to `s3_service.upload_file()` | Active |
| D-08 | 2026-08 | Frontend never sets a manual `multipart/form-data` Content-Type; axios sets the boundary | A manual header strips the multipart boundary and breaks uploads in the browser | Active |
