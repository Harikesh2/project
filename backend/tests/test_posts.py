import pytest
from fastapi.testclient import TestClient

def test_create_post(client: TestClient):
    """Test creating a post"""
    # 1. Create the user profile first (needed for posts count and metadata)
    client.post("/api/users", json={
        "username": "author_user",
        "email": "author@example.com"
    })
    
    # 2. Create post
    payload = {
        "content": "This is a test post!",
        "image_url": "http://example.com/post.jpg"
    }
    response = client.post("/api/posts", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "post_id" in data
    assert data["content"] == "This is a test post!"
    assert data["image_url"] == "http://example.com/post.jpg"
    assert data["likes_count"] == 0
    assert data["comments_count"] == 0
    assert data["user_id"] == "test_user_123"

def test_get_post_by_id(client: TestClient):
    """Test retrieving a post by ID"""
    client.post("/api/users", json={
        "username": "author_user",
        "email": "author@example.com"
    })
    
    # Create post
    create_response = client.post("/api/posts", json={"content": "Hello World"})
    post_id = create_response.json()["post_id"]
    
    # Get post
    response = client.get(f"/api/posts/{post_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == post_id
    assert data["content"] == "Hello World"
    assert "user" in data
    assert data["user"]["username"] == "author_user"

def test_update_and_delete_post(client: TestClient):
    """Test updating and deleting a post"""
    client.post("/api/users", json={
        "username": "author_user",
        "email": "author@example.com"
    })
    
    create_response = client.post("/api/posts", json={"content": "Original Post"})
    post_id = create_response.json()["post_id"]
    
    # Update post
    update_response = client.put(f"/api/posts/{post_id}", json={"content": "Updated Post"})
    assert update_response.status_code == 200
    assert update_response.json()["content"] == "Updated Post"
    
    # Delete post
    delete_response = client.delete(f"/api/posts/{post_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Post deleted successfully"}
    
    # Verify post is gone
    response = client.get(f"/api/posts/{post_id}")
    assert response.status_code == 404

def test_like_and_unlike_post(client: TestClient):
    """Test liking and unliking a post"""
    client.post("/api/users", json={
        "username": "author_user",
        "email": "author@example.com"
    })
    
    create_response = client.post("/api/posts", json={"content": "Liking this"})
    post_id = create_response.json()["post_id"]
    
    # Like
    like_response = client.post(f"/api/posts/{post_id}/like")
    assert like_response.status_code == 200
    assert like_response.json()["liked"] is True
    
    # Verify count is 1
    get_response = client.get(f"/api/posts/{post_id}")
    assert get_response.json()["likes_count"] == 1
    
    # Unlike
    unlike_response = client.post(f"/api/posts/{post_id}/like")
    assert unlike_response.status_code == 200
    assert unlike_response.json()["liked"] is False
    
    # Verify count is 0
    get_response = client.get(f"/api/posts/{post_id}")
    assert get_response.json()["likes_count"] == 0

def test_get_feed(client: TestClient):
    """Test timelines feed retrieval"""
    client.post("/api/users", json={
        "username": "author_user",
        "email": "author@example.com"
    })
    
    # Create a couple of posts
    client.post("/api/posts", json={"content": "Post 1"})
    client.post("/api/posts", json={"content": "Post 2"})
    
    # Get feed
    response = client.get("/api/posts/feed")
    assert response.status_code == 200
    feed = response.json()
    assert len(feed) >= 2
    # Verify sorted by created_at descending (newest first)
    assert feed[0]["content"] == "Post 2"
    assert feed[1]["content"] == "Post 1"

def test_post_comments(client: TestClient):
    """Test adding, listing and deleting comments on a post"""
    client.post("/api/users", json={
        "username": "author_user",
        "email": "author@example.com"
    })
    
    create_response = client.post("/api/posts", json={"content": "Commenting on this"})
    post_id = create_response.json()["post_id"]
    
    # 1. Add comment
    comment_payload = {"content": "This is a great post!"}
    comment_response = client.post(f"/api/posts/{post_id}/comments", json=comment_payload)
    assert comment_response.status_code == 200
    comment_data = comment_response.json()
    assert comment_data["content"] == "This is a great post!"
    assert comment_data["post_id"] == post_id
    assert comment_data["user_id"] == "test_user_123"
    comment_id = comment_data["comment_id"]
    
    # 2. Get comments
    comments_response = client.get(f"/api/posts/{post_id}/comments")
    assert comments_response.status_code == 200
    comments_list = comments_response.json()
    assert len(comments_list) == 1
    assert comments_list[0]["content"] == "This is a great post!"
    assert comments_list[0]["user"]["username"] == "author_user"
    
    # 3. Delete comment
    delete_response = client.delete(f"/api/posts/{post_id}/comments/{comment_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Comment deleted successfully"}
    
    # Verify comments list is now empty
    comments_response = client.get(f"/api/posts/{post_id}/comments")
    assert len(comments_response.json()) == 0


def test_legacy_timeline_post_edit_search_like_comments(client: TestClient):
    """Legacy posts (USER#/POST#{id} only) support get, edit, search, like, and comments."""
    from datetime import datetime
    from app.database.connection import db_connection
    from app.core.config import settings

    client.post("/api/users", json={
        "username": "legacy_author",
        "email": "legacy@example.com",
    })

    post_id = "legacy-post-abc-123"
    now = datetime.utcnow().isoformat()
    legacy_item = {
        "Pk": "USER#test_user_123",
        "Sk": f"POST#{post_id}",
        "post_id": post_id,
        "user_id": "test_user_123",
        "content": "Legacy searchable post content",
        "created_at": now,
        "updated_at": now,
        "likes_count": 0,
        "comments_count": 0,
    }

    table = db_connection.resource.Table(settings.social_media_table)
    table.put_item(Item=legacy_item)

    # Get by ID (lazy-migrates to POST#/METADATA)
    get_response = client.get(f"/api/posts/{post_id}")
    assert get_response.status_code == 200
    assert get_response.json()["content"] == "Legacy searchable post content"

    # Search finds legacy timeline item
    search_response = client.get("/api/posts/search", params={"q": "Legacy searchable"})
    assert search_response.status_code == 200
    assert any(p["post_id"] == post_id for p in search_response.json())

    # Edit
    update_response = client.put(
        f"/api/posts/{post_id}",
        json={"content": "Legacy post updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"] == "Legacy post updated"

    # Like
    like_response = client.post(f"/api/posts/{post_id}/like")
    assert like_response.status_code == 200
    assert like_response.json()["liked"] is True
    assert client.get(f"/api/posts/{post_id}").json()["likes_count"] == 1

    # Comment
    comment_response = client.post(
        f"/api/posts/{post_id}/comments",
        json={"content": "Comment on legacy post"},
    )
    assert comment_response.status_code == 200
    comments_response = client.get(f"/api/posts/{post_id}/comments")
    assert comments_response.status_code == 200
    assert len(comments_response.json()) == 1
    assert comments_response.json()[0]["content"] == "Comment on legacy post"

    # Delete
    delete_response = client.delete(f"/api/posts/{post_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Post deleted successfully"}
    assert client.get(f"/api/posts/{post_id}").status_code == 404
