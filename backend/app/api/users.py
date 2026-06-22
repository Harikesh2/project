from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional

from app.auth.clerk import get_current_user
from app.models.user import User, UserCreate, UserUpdate, UserSearch
from app.services.user_service import user_service
from app.services.follow_service import follow_service

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
    """
    Create a new user profile for the authenticated user.
    
    This endpoint takes the user details and registers them under the authenticated user's ID.
    """
    return await _create_authenticated_user_profile(user_data, current_user)


@router.post(
    "/me",
    response_model=User,
    summary="Create profile for the current authenticated user (Deprecated)",
    description=(
        "Deprecated alias for POST /api/users. It creates the same authenticated user's "
        "profile and is kept only for backward compatibility."
    ),
    deprecated=True,
    response_description="The created user profile"
)
async def create_current_user_profile_deprecated(
    user_data: UserCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Deprecated: use POST /api/users to create the authenticated user's profile."""
    return await _create_authenticated_user_profile(user_data, current_user)


@router.get("/me", response_model=User)
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get current user profile"""
    user = await user_service.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/me", response_model=User)
async def update_current_user(
    user_data: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update current user profile"""
    user = await user_service.update_user(current_user["user_id"], user_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


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
