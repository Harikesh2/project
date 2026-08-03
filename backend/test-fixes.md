# Test Fixes — CI/CD

Branch: `websocket` | Goal: get `pytest` green in CI

---

## How to reproduce locally

1. Start DynamoDB Local (must be running on port 8001):
   ```bash
   docker run -d --name dynamodb-local -p 8001:8000 amazon/dynamodb-local:latest
   ```

2. Run the full suite from `backend/`:
   ```bash
   python -m pytest -v
   ```

3. CI command (matches GitHub Actions `.github/workflows/backend-ci.yml`):
   ```bash
   python -m pytest -v --cov=app --cov-report=term-missing
   ```

## Baseline

- [x] First full run — `1 failed, 23 passed` (Phase 4 fixed → `24 passed`)
- Local note: tested with Python 3.14 + newer pydantic (`pydantic>=2.10`) because pinned `pydantic==2.5.0` cannot build on 3.14. CI uses Python 3.11 with the pinned requirements — expected green.

---

## Phase 1: `tests/test_users.py`

| Test | Failure | Root cause | Fix | Status |
|------|---------|------------|-----|--------|
| (all pass) | — | — | — | [x] |

## Phase 2: `tests/test_posts.py`

| Test | Failure | Root cause | Fix | Status |
|------|---------|------------|-----|--------|
| (all pass) | — | — | — | [x] |

## Phase 3: `tests/test_upload.py`

| Test | Failure | Root cause | Fix | Status |
|------|---------|------------|-----|--------|
| (all pass) | — | — | — | [x] |

## Phase 4: `tests/test_chat.py`

| Test | Failure | Root cause | Fix | Status |
|------|---------|------------|-----|--------|
| `test_build_conversation_id` | `assert id_1.startswith("DM#")` → False | Test asserted old `DM#`-prefixed ID, but `build_conversation_id` deliberately returns a bare SHA-256 hex digest — the `#` broke frontend URL routing (browser strips `#` fragments). See docstring in `app/models/chat.py:15-27`. | Test updated: assert `len == 64` + `isalnum()` instead of prefix | [x] |

## Phase 5: CI workflow issues

- [x] DynamoDB container / port mapping matches `conftest.py` (expects `http://localhost:8001`)
- [x] Environment variables match `conftest.py` defaults
- [x] Docker build step (`docker build -t social-media-backend:latest .`) succeeds — fixed by adding `.dockerignore` (broken Windows `venv/` with dangling `lib64` symlink broke the build context)
- [x] Added `backend/.dockerignore` — excludes `venv/`, `.env`, tests, and caches from the build context (also prevents `.env` secrets from being baked into the image)

---

## Acceptance

- [x] `pytest -v` fully green locally (`24 passed`)
- [x] Docker build passes (`social-media-backend:latest`)
- [ ] CI run passes (push to GitHub to confirm)
