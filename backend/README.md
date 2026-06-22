# Social Media Backend

FastAPI backend with AWS DynamoDB and Clerk authentication.

## Prerequisites

- Python 3.11+
- AWS credentials or local DynamoDB (via Docker)

## Setup

1. Copy environment file:
   ```powershell
   copy .env.example .env
   ```

2. Fill in `.env` with your Clerk secret key and AWS credentials.

3. Install dependencies and start the server:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   python run_setup.py
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Docker

Run backend with local DynamoDB:
```powershell
docker-compose up --build
```

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- DynamoDB local: http://localhost:8001
- DynamoDB admin UI: http://localhost:8002

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/users` | Create the authenticated user's profile |
| POST | `/api/users/me` | Deprecated alias for `POST /api/users` |
| GET | `/api/users/me` | Current user profile |
| PUT | `/api/users/me` | Update profile |
| GET | `/api/users/{user_id}` | User profile |
| GET | `/api/posts/feed` | Timeline feed |
| POST | `/api/posts` | Create post |
| POST | `/api/posts/{post_id}/like` | Like/unlike |
| POST | `/api/users/{user_id}/follow` | Follow/unfollow |

All protected routes require a valid Clerk JWT token.
