# Social Media Backend

FastAPI backend with AWS DynamoDB and Clerk authentication.

## Features & Optimizations

- **Security Hardening**:
  - **S3 Image Upload Auth Guard**: Secured the S3 upload endpoint (`/api/upload-image`) using Clerk authentication validation.
  - **Endpoint Deregistration**: Safely removed raw, public database read/write `/api/socialmedia` endpoints to eliminate exposure risks.
- **Database Performance (DynamoDB)**:
  - **GSI Query Optimizations**: Swapped out table-wide Scan operations in favor of highly optimized GSI queries on `GSI1-post-id-index` (for individual posts) and `GSI3-followers-index` (for follower lists).
- **Core Platform Features**:
  - **S3 Profile Avatar Uploads**: Added the `POST /api/users/me/avatar` endpoint to support direct-to-S3 avatar image uploads.
  - **Flexible Layout Navigation**: Standardized navigation layout components with optional logout functions on the frontend.

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

## AWS Integration Details

### AWS Setup

Required environment variables in your `.env` file:

```env
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=ap-south-1
```

### Verifying Credentials

To verify your AWS configuration and credentials outside the backend application environment, run the following command in PowerShell:

```powershell
python -c "import boto3; print(boto3.client('sts').get_caller_identity())"
```

### Running the Backend

Start the FastAPI application with `uvicorn`:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### AWS Health Check

To inspect the status of the AWS integration, call the following health endpoint:

```http
GET /health/aws
```

#### Example Success Response:

```json
{
  "status": "ok",
  "aws": {
    "account": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/social-media-app-user",
    "region": "ap-south-1"
  }
}
```

### Troubleshooting

- **`InvalidClientTokenId` / `Security token included in request is invalid`**
  - **Reason**: The AWS access key or secret key values in `.env` are malformed or invalid. A common issue is a trailing space or a stale session token (e.g. `AWS_SESSION_TOKEN`) being present in the operating system environment.
  - **Solution**: Check `.env` values carefully. Run `Remove-Item Env:AWS_SESSION_TOKEN` in PowerShell to clear stale session tokens.
- **`Missing AWS_REGION`**
  - **Reason**: The `AWS_REGION` variable is not set or empty in `.env`.
  - **Solution**: Add `AWS_REGION=ap-south-1` (or your preferred region) to `.env`.
- **`Missing DynamoDB table`**
  - **Reason**: The backend attempts to connect to DynamoDB tables that do not exist (e.g., `ResourceNotFoundException`).
  - **Solution**: Run the setup script `python run_setup.py` to automatically create all required tables.
- **`AccessDeniedException` / `AccessDenied`**
  - **Reason**: The IAM user/role associated with the AWS keys does not have permissions to perform required DynamoDB actions (e.g. `GetItem`, `PutItem`, `Query`).
  - **Solution**: Attach a policy allowing DynamoDB read/write access to the specific tables on the IAM user.
- **`Credentials changed but server not restarted`**
  - **Reason**: Uvicorn only loads environment variables from `.env` once on startup. Modifying `.env` while the server is running will not update the credentials.
  - **Solution**: Stop the server (`Ctrl+C`) and start it again.

