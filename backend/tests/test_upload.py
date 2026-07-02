import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

def test_upload_image_success(client: TestClient):
    """Test successful image upload"""
    with patch("app.api.upload.s3_service.upload_file") as mock_upload:
        # Mock S3 response
        mock_upload.return_value = {
            "url": "https://test-bucket.s3.us-east-1.amazonaws.com/uploads/mock-key.png",
            "key": "uploads/mock-key.png"
        }
        
        file_content = b"fake image data"
        files = {"file": ("avatar.png", file_content, "image/png")}
        
        response = client.post("/api/upload-image", files=files)
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Upload successful"
        assert data["url"] == "https://test-bucket.s3.us-east-1.amazonaws.com/uploads/mock-key.png"
        assert data["key"] == "uploads/mock-key.png"
        
        # Verify s3_service.upload_file was called with expected arguments
        mock_upload.assert_called_once_with(
            file_content=file_content,
            file_name="avatar.png",
            content_type="image/png",
            user_id="test_user_123",
        )

def test_upload_image_invalid_extension(client: TestClient):
    """Test image upload failure due to unsupported content type"""
    files = {"file": ("document.txt", b"plain text content", "text/plain")}
    
    response = client.post("/api/upload-image", files=files)
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]

def test_upload_image_too_large(client: TestClient):
    """Test image upload failure due to file size exceeding limit (5MB)"""
    # Create file content larger than 5MB
    large_content = b"0" * (5 * 1024 * 1024 + 1)
    files = {"file": ("large_image.jpg", large_content, "image/jpeg")}
    
    response = client.post("/api/upload-image", files=files)
    assert response.status_code == 400
    assert "too large" in response.json()["detail"]


def test_upload_avatar_success(client: TestClient):
    """Test avatar upload auto-creates user and stores URL in profile."""
    with patch("app.api.users.s3_service.upload_file") as mock_upload:
        mock_upload.return_value = {
            "url": "https://test-bucket.s3.us-east-1.amazonaws.com/uploads/test_user_123/mock-avatar.png",
            "key": "uploads/test_user_123/mock-avatar.png",
        }

        file_content = b"fake avatar data"
        files = {"file": ("avatar.png", file_content, "image/png")}

        response = client.post("/api/users/me/avatar", files=files)
        assert response.status_code == 200

        data = response.json()
        assert data["user_id"] == "test_user_123"
        assert data["avatar_url"] == mock_upload.return_value["url"]

        mock_upload.assert_called_once_with(
            file_content=file_content,
            file_name="avatar.png",
            content_type="image/png",
            user_id="test_user_123",
        )
