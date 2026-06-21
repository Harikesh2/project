import os
import sys

# Set testing environment variables before importing any app modules
os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
os.environ["AWS_SECRET_ACCESS_KEY"] = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_ENDPOINT_URL"] = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8001")
os.environ["DYNAMODB_TABLE_PREFIX"] = "test_social_media"
os.environ["CLERK_SECRET_KEY"] = "test_clerk_secret"
os.environ["CLERK_JWKS_URL"] = "http://localhost/jwks"
os.environ["CLERK_ISSUER"] = "http://localhost"
os.environ["S3_BUCKET_NAME"] = "test-bucket"

# Add parent directory to path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.auth.clerk import get_current_user
from app.database.connection import db_connection
from app.database.setup import create_all_tables
from app.core.config import settings

# Mock User Claims
MOCK_USER = {
    "user_id": "test_user_123",
    "email": "test@example.com",
    "username": "test_user",
    "claims": {
        "sub": "test_user_123",
        "email": "test@example.com",
        "username": "test_user"
    }
}

# Override auth dependency
async def override_get_current_user():
    return MOCK_USER

@pytest.fixture(scope="session")
def event_loop():
    """Create session-wide event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

def delete_all_tables():
    """Synchronously delete all test tables"""
    resource = db_connection.resource
    table_names = [
        settings.users_table,
        settings.posts_table,
        settings.follows_table,
        settings.likes_table,
        settings.comments_table
    ]
    for name in table_names:
        try:
            table = resource.Table(name)
            table.delete()
            table.wait_until_not_exists()
        except Exception:
            pass

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create test tables at the start of the session, and clean up at the end"""
    print("\n--- DIAGNOSTIC DB SETUP ---")
    print("settings.dynamodb_endpoint_url:", settings.dynamodb_endpoint_url)
    print("settings.aws_access_key_id:", settings.aws_access_key_id)
    print("settings.aws_secret_access_key:", settings.aws_secret_access_key)
    print("settings.dynamodb_table_prefix:", settings.dynamodb_table_prefix)
    print("---------------------------\n")
    # Force delete tables in case a previous run crashed and left them
    delete_all_tables()
    
    # Create all tables
    try:
        create_all_tables()
    except Exception as e:
        pytest.fail(f"Could not connect to local DynamoDB or create tables. Ensure DynamoDB Local is running. Error: {e}")
        
    yield
    
    # Clean up tables
    delete_all_tables()

@pytest.fixture(autouse=True)
def clear_db():
    """Clear all records from all tables before each test to ensure test isolation"""
    resource = db_connection.resource
    table_names = [
        settings.users_table,
        settings.posts_table,
        settings.follows_table,
        settings.likes_table,
        settings.comments_table
    ]
    
    for name in table_names:
        try:
            table = resource.Table(name)
            # Scan all items
            response = table.scan()
            
            # Find the primary keys for deletion
            keys = [k['AttributeName'] for k in table.key_schema]
            
            # Delete items using batch writer
            with table.batch_writer() as batch:
                for item in response.get('Items', []):
                    key_to_delete = {k: item[k] for k in keys}
                    batch.delete_item(Key=key_to_delete)
        except Exception as e:
            print(f"Error clearing table {name}: {e}")

@pytest.fixture
def client():
    """FastAPI TestClient with overridden authentication"""
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
