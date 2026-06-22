# pyrefly: ignore [missing-import]
import pytest
from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_create_and_get_user_profile(client: TestClient):
    """Test creating and retrieving own user profile"""
    # 1. Profile should not exist initially
    response = client.get("/api/users/me")
    assert response.status_code == 404
    
    # 2. Create profile
    payload = {
        "username": "test_user",
        "email": "test@example.com",
        "avatar_url": "http://example.com/avatar.jpg",
        "bio": "I am a test user"
    }
    response = client.post("/api/users", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user_123"
    assert data["username"] == "test_user"
    assert data["email"] == "test@example.com"
    assert data["avatar_url"] == "http://example.com/avatar.jpg"
    assert data["bio"] == "I am a test user"
    assert data["followers_count"] == 0
    assert data["following_count"] == 0
    
    # 3. Retrieve profile again
    response = client.get("/api/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user_123"
    assert data["username"] == "test_user"

def test_update_user_profile(client: TestClient):
    """Test updating user profile"""
    # Create profile
    payload = {
        "username": "test_user",
        "email": "test@example.com",
        "bio": "Old bio"
    }
    client.post("/api/users", json=payload)
    
    # Update profile
    update_payload = {
        "username": "updated_user",
        "bio": "New bio",
        "avatar_url": "http://example.com/new.jpg"
    }
    response = client.put("/api/users/me", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "updated_user"
    assert data["bio"] == "New bio"
    assert data["avatar_url"] == "http://example.com/new.jpg"

def test_get_user_by_id(client: TestClient):
    """Test retrieving user by ID"""
    # Create user profile
    payload = {
        "username": "alice",
        "email": "alice@example.com",
        "bio": "Alice bio"
    }
    # Create profile (this creates it for test_user_123)
    client.post("/api/users", json=payload)
    
    response = client.get("/api/users/test_user_123")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user_123"
    assert data["username"] == "alice"
    assert data["bio"] == "Alice bio"

def test_search_users(client: TestClient):
    """Test searching users by username"""
    # 1. Create test_user_123
    client.post("/api/users", json={
        "username": "alice_smith",
        "email": "alice@example.com",
        "bio": "Alice bio"
    })
    
    # To create another user, we bypass dependency injection and insert into DB directly if we want,
    # or we can override the authentication headers / claims for another request.
    # But even with one user, we can verify that search works!
    response = client.get("/api/users/search", params={"q": "alice"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["username"] == "alice_smith"
    assert data[0]["user_id"] == "test_user_123"
    
    # Search for non-existent user
    response = client.get("/api/users/search", params={"q": "bob"})
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_follow_and_unfollow_user(client: TestClient):
    """Test following and unfollowing a user"""
    # 1. Create current user profile
    client.post("/api/users", json={
        "username": "follower_user",
        "email": "follower@example.com"
    })
    
    # 2. Create another user in DB directly using UserService
    from app.services.user_service import user_service
    from app.models.user import UserCreate
    import asyncio
    
    async def create_target_user():
        return await user_service.create_user(
            UserCreate(username="target_user", email="target@example.com"),
            "target_user_456"
        )
    
    # Run async function inside test
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_target_user())
    
    # 3. Follow the target user
    response = client.post("/api/users/target_user_456/follow")
    assert response.status_code == 200
    assert response.json() == {"followed": True}
    
    # Verify follow status / counts
    response = client.get("/api/users/test_user_123")
    assert response.status_code == 200
    # Current user's profile gets updated on follow? Wait, followers count is of the target user!
    # Let's verify target user's followers count has incremented to 1
    response = client.get("/api/users/target_user_456")
    assert response.status_code == 200
    assert response.json()["followers_count"] == 1
    
    # 4. Unfollow the target user
    response = client.post("/api/users/target_user_456/unfollow")
    assert response.status_code == 200
    assert response.json() == {"unfollowed": True}
    
    # Verify followers count has decremented back to 0
    response = client.get("/api/users/target_user_456")
    assert response.status_code == 200
    assert response.json()["followers_count"] == 0

def test_create_profile_deprecated_endpoint(client: TestClient):
    """Test creating own user profile using the deprecated POST /api/users/me endpoint"""
    response = client.get("/api/users/me")
    assert response.status_code == 404

    payload = {
        "username": "deprecated_tester",
        "email": "deprecated@example.com",
        "bio": "Testing deprecated endpoint"
    }
    response = client.post("/api/users/me", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user_123"
    assert data["username"] == "deprecated_tester"

def test_create_profile_deprecated_endpoint_uses_same_conflict_behavior(client: TestClient):
    """Deprecated create endpoint should share canonical creation behavior."""
    payload = {
        "username": "alias_tester",
        "email": "alias@example.com",
        "bio": "Testing deprecated endpoint conflict handling"
    }
    response = client.post("/api/users/me", json=payload)
    assert response.status_code == 200

    response2 = client.post("/api/users/me", json=payload)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "User already exists"

def test_create_user_profile_already_exists(client: TestClient):
    """Test that creating a profile when one already exists returns a 400 Bad Request"""
    payload = {
        "username": "tester_1",
        "email": "tester1@example.com",
        "bio": "Initial profile"
    }
    response = client.post("/api/users", json=payload)
    assert response.status_code == 200

    # Try creating profile again for the same authenticated user ID
    response2 = client.post("/api/users", json=payload)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "User already exists"

def test_create_user_openapi_marks_only_me_alias_deprecated(client: TestClient):
    """OpenAPI should show POST /api/users as canonical and POST /api/users/me as deprecated."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    create_user = paths["/api/users"]["post"]
    create_user_me = paths["/api/users/me"]["post"]

    assert create_user.get("deprecated") is not True
    assert create_user_me["deprecated"] is True
    assert create_user["responses"]["200"]["content"]["application/json"]["schema"] == (
        create_user_me["responses"]["200"]["content"]["application/json"]["schema"]
    )
