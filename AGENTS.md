# AGENTS.md — Social Media App

Instructions for AI agents working in this repository.

## Project

A social media platform with user profiles, posts, likes, comments, follows, search, chat, notifications, and S3 image uploads.

- **Backend**: FastAPI + DynamoDB (single-table `SocialMedia` design), Clerk JWT auth, S3 uploads, WebSockets for chat/notifications
- **Frontend**: React + TypeScript (Vite), Clerk auth, axios API layer

## Layout

```
backend/app/
  api/         FastAPI routers (users, posts, upload, chat, notifications, ...)
  auth/        Clerk JWT verification
  core/        Config
  database/    DynamoDB connection + table setup
  models/      Pydantic API models + DynamoDB item models (single-table keys)
  services/    Business logic (user, post, follow, like, comment, chat, notification, s3)
backend/tests/ pytest suite (needs DynamoDB Local on http://localhost:8001)
frontend/src/
  components/  UI components
  pages/       Routes (Home, Profile, Search, Chat, Notifications, ...)
  services/    axios API clients
  types/       TypeScript API types
```

## Key conventions

- **Single-table DynamoDB**: composite keys `Pk`/`Sk`, item prefixes (`USER#`, `POST#`, `LIKE#`, `COMMENT#`, `FOLLOWING#`, `FOLLOWER#`), 3 GSIs. The `SocialMedia` table is the only table.
- **Dual-write pattern**: follows, likes, and comments write duplicated items on both the user and target partitions.
- **REST API contract is stable** — frontend depends on it; never break response shapes.

## Commands

```bash
# Backend
cd backend
python -m app.database.setup          # create the SocialMedia table
python -m pytest tests/ -v            # run tests (needs DynamoDB Local on :8001)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm run dev      # dev server (port 5173)
npm run build    # typecheck + production build
npm run lint     # eslint
```

## Docs workflow (strict — mandatory)

1. `project-changes.md` is the single source of truth for plan + phase status (one phase at a time: NOT STARTED → IN PROGRESS → COMPLETED).
2. Every technical decision is logged in `DECISIONS.md` (append-only, D-XX numbering, never delete).
3. Log ALL phase changes in `project-changes.md` (files touched, changes, verification/gate result).
4. Implement ONE phase at a time; run its gate before marking COMPLETED.
5. On completion, flip the feature's status in `FEATURES.md`, then move to the next phase.
6. No scope creep — anything new = new decision + new phase.
