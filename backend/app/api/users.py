from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from typing import List, Dict, Any, Optional

from app.auth.clerk import get_current_user
from app.models.user import User, UserCreate, UserUpdate, UserSearch, UserProfile
from app.services.user_service import user_service
from app.services.follow_service import follow_service
from app.services.s3_service import s3_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])


async def _create_authenticated_user_profile(
    user_data: UserCreate,
    current_user: Dict[str, Any]
) -> User:
    """Create the profile owned by the authenticated user."""
    try:
        return await user_service.create_user(user_data, current_user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "",
    response_model=User,
    summary="Create a new user profile",
    description=(
        "Create the profile for the authenticated user. "
        "Use this canonical endpoint instead of the deprecated POST /api/users/me alias."
    ),
    response_description="The created user profile"
)
async def create_user(
    user_data: UserCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new user"""
    user_id = current_user["user_id"]
    logger.info(f"User creation requested for user_id: {user_id}")
    user = await _create_authenticated_user_profile(user_data, current_user)
    logger.info(f"Successfully created user entry in database for user_id: {user_id}")
    return user


async def _auto_create_user_from_claims(current_user: Dict[str, Any]) -> User:
    """Helper function to auto-create user in DynamoDB from Clerk JWT claims."""
    user_id = current_user["user_id"]
    logger.info(f"User {user_id} not found — auto-creating from Clerk claims.")

    # Build a safe username from whatever Clerk provides.
    # Clerk 'username' claim is set only if enabled in the Clerk dashboard;
    # fallback to the first segment of the email, then a short suffix of the user_id.
    claims = current_user.get("claims", {})
    raw_username = (
        current_user.get("username")
        or claims.get("username")
        or claims.get("preferred_username")
    )
    email = (
        current_user.get("email")
        or claims.get("email")
        or claims.get("email_address")
        or f"{user_id}@placeholder.local"
    )

    if not raw_username:
        # Derive a safe username from the email local-part
        local_part = email.split("@")[0]
        # Keep only alphanumeric + underscores, trim to 25 chars
        safe_local = "".join(c if c.isalnum() or c == "_" else "_" for c in local_part)[:25]
        raw_username = safe_local or f"user_{user_id[-6:]}"

    # Enforce Pydantic min/max constraints (3–30 chars)
    username = raw_username[:30]
    if len(username) < 3:
        username = f"user_{user_id[-6:]}"

    try:
        user_data = UserCreate(username=username, email=email)
        user = await user_service.create_user(user_data, user_id=user_id)
        logger.info(f"Auto-created user {user_id} with username='{username}'")
        return user
    except ValueError:
        # ConditionalCheckFailedException — race condition, record now exists
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create or retrieve user record.")
        return user


@router.post(
    "/me",
    response_model=User,
    deprecated=True,
    summary="Create user profile (deprecated)",
    description="Deprecated alias for POST /api/users. Use POST /api/users instead.",
    response_description="The created user profile",
)
async def create_user_me_alias(
    user_data: UserCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new user via the deprecated /me alias."""
    return await _create_authenticated_user_profile(user_data, current_user)


@router.get("/me", response_model=User)
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get current user profile.
    Auto-creates the user record on first login using Clerk JWT claims
    so the client never needs to call POST /api/users separately.
    """
    user_id = current_user["user_id"]
    logger.info(f"Retrieving profile for user_id: {user_id}")
    user = await user_service.get_user_by_id(user_id)

    if not user:
        user = await _auto_create_user_from_claims(current_user)

    logger.info(f"Returning profile for user_id: {user_id}")
    return user


# Bug 3 Fix: Add PUT /me route so frontend's PUT /users/me works
@router.put("/me", response_model=User)
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update current user's own profile"""
    user_id = current_user["user_id"]
    logger.info(f"Updating profile for user_id: {user_id}")
    user = await user_service.update_user(user_id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/me/avatar", response_model=User)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload a profile avatar image to S3 and update the user record."""
    user_id = current_user["user_id"]

    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: JPEG, PNG, WEBP."
        )

    MAX_SIZE = 2 * 1024 * 1024  # 2 MB
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 2 MB.")

    logger.info(f"Uploading avatar for user_id: {user_id}, file: {file.filename}, size: {len(contents)} bytes")

    try:
        result = s3_service.upload_file(
            file_content=contents,
            file_name=file.filename or "avatar.png",
            content_type=file.content_type,
            user_id=user_id,
        )
    except Exception as exc:
        logger.error(f"Avatar S3 upload failed for {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again.")
    finally:
        await file.close()

    avatar_url = result["url"]
    logger.info(f"Avatar uploaded to S3: {avatar_url}")

    user = await user_service.get_user_by_id(user_id)
    if not user:
        user = await _auto_create_user_from_claims(current_user)

    user = await user_service.update_user(user_id, UserUpdate(avatar_url=avatar_url))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"Avatar updated for user_id: {user_id}")
    return user


# NOTE: /search MUST be declared BEFORE /{user_id} so FastAPI matches it correctly.
@router.get("/search", response_model=List[UserSearch])
async def search_users(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Search users by username or bio"""
    users = await user_service.search_users(q, limit)
    return [UserSearch.from_user(user) for user in users]


# Bug 1 Fix: Return full UserProfile (not UserSearch) with is_following populated
@router.get("/{user_id}", response_model=UserProfile)
async def get_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user profile by ID"""
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if current user is following this user
    current_user_id = current_user["user_id"]
    is_following = False
    is_followed_by = False
    if current_user_id != user_id:
        is_following = await follow_service.is_following(current_user_id, user_id)
        is_followed_by = await follow_service.is_following(user_id, current_user_id)

    return UserProfile(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        created_at=user.created_at,
        updated_at=user.updated_at,
        followers_count=user.followers_count,
        following_count=user.following_count,
        posts_count=user.posts_count,
        is_following=is_following,
        is_followed_by=is_followed_by,
    )


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user profile (only by owner)"""
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this user")

    user = await user_service.update_user(user_id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete user account (only by owner)"""
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this user")

    success = await user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}


# Bug 2 Fix: Return {"following": ..., "success": ...} instead of {"followed": ...}
@router.post("/{user_id}/follow")
async def follow_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Follow or unfollow a user (toggle)"""
    if current_user["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    # Check if target user exists
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_user_id = current_user["user_id"]
    already_following = await follow_service.is_following(current_user_id, user_id)

    if already_following:
        # Unfollow
        await follow_service.unfollow_user(current_user_id, user_id)
        return {"following": False, "success": True}
    else:
        # Follow
        success = await follow_service.follow_user(current_user_id, user_id)
        return {"following": success, "success": True}


@router.post("/{user_id}/unfollow")
async def unfollow_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Unfollow a user"""
    if current_user["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot unfollow yourself")

    success = await follow_service.unfollow_user(current_user["user_id"], user_id)
    return {"unfollowed": success}


@router.get("/{user_id}/followers", response_model=List[UserSearch])
async def get_followers(
    user_id: str,
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get followers of a user"""
    followers = await follow_service.get_followers(user_id, limit)
    return [UserSearch.from_user(follower) for follower in followers]


@router.get("/{user_id}/following", response_model=List[UserSearch])
async def get_following(
    user_id: str,
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get users that a user is following"""
    following = await follow_service.get_following(user_id, limit)
    return [UserSearch.from_user(user) for user in following]
