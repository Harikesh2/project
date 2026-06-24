from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional

from app.auth.clerk import get_current_user
from app.models.user import User, UserCreate, UserUpdate, UserSearch
from app.services.user_service import user_service
from app.services.follow_service import follow_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])


@router.post("", response_model=User)
async def create_user(
    user_data: UserCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new user"""
    user_id = current_user["user_id"]
    logger.info(f"User creation requested for user_id: {user_id}")
    user = await user_service.create_user(user_data, user_id=user_id)
    logger.info(f"Successfully created user entry in database for user_id: {user_id}")
    return user


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
        except ValueError:
            # ConditionalCheckFailedException — race condition, record now exists
            user = await user_service.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status_code=500, detail="Failed to create or retrieve user record.")

    logger.info(f"Returning profile for user_id: {user_id}")
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
    return [
        UserSearch(
            user_id=user.user_id,
            username=user.username,
            avatar_url=user.avatar_url,
            bio=user.bio,
            followers_count=user.followers_count
        )
        for user in users
    ]


@router.get("/{user_id}", response_model=UserSearch)
async def get_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user profile by ID"""
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserSearch(
        user_id=user.user_id,
        username=user.username,
        avatar_url=user.avatar_url,
        bio=user.bio,
        followers_count=user.followers_count
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


@router.post("/{user_id}/follow")
async def follow_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Follow a user"""
    if current_user["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    # Check if target user exists
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    success = await follow_service.follow_user(current_user["user_id"], user_id)
    return {"followed": success}


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
    return [
        UserSearch(
            user_id=follower.user_id,
            username=follower.username,
            avatar_url=follower.avatar_url,
            bio=follower.bio,
            followers_count=follower.followers_count
        )
        for follower in followers
    ]


@router.get("/{user_id}/following", response_model=List[UserSearch])
async def get_following(
    user_id: str,
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get users that a user is following"""
    following = await follow_service.get_following(user_id, limit)
    return [
        UserSearch(
            user_id=user.user_id,
            username=user.username,
            avatar_url=user.avatar_url,
            bio=user.bio,
            followers_count=user.followers_count
        )
        for user in following
    ]