from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional

from app.auth.clerk import get_current_user
from app.models.post import Post, PostCreate, PostUpdate, PostWithUser
from app.models.comment import Comment, CommentCreate, CommentWithUser
from app.services.post_service import post_service
from app.services.follow_service import follow_service

router = APIRouter(tags=["posts"])


@router.post("", response_model=Post)
async def create_post(
    post_data: PostCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new post"""
    post = await post_service.create_post(post_data, current_user["user_id"])
    return post


@router.get("/feed", response_model=List[PostWithUser])
async def get_feed(
    limit: int = Query(20, ge=1, le=50),
    last_key: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get timeline feed of posts from followed users"""
    # Get list of users that current user follows
    following_ids = await follow_service.get_following_ids(current_user["user_id"])
    
    # Include current user's posts in feed
    following_ids.append(current_user["user_id"])
    
    if not following_ids:
        return []
    
    # For simplicity, we'll get recent posts from all followed users
    # In production, you'd want a more sophisticated feed algorithm
    all_posts = []
    
    for user_id in following_ids:
        posts = await post_service.get_user_posts(user_id, limit=10)
        all_posts.extend(posts)
    
    # Sort by created_at descending and limit
    all_posts.sort(key=lambda x: x.created_at, reverse=True)
    return all_posts[:limit]


@router.get("/user/{user_id}", response_model=List[PostWithUser])
async def get_user_posts(
    user_id: str,
    limit: int = Query(20, ge=1, le=50),
    last_key: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get posts by a specific user"""
    posts = await post_service.get_user_posts(user_id, limit, last_key)
    return posts

@router.get("/search", response_model=List[PostWithUser])
async def search_posts(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Search posts by content"""
    posts = await post_service.search_posts(q, limit)
    return posts


@router.get("/{post_id}", response_model=PostWithUser)
async def get_post(
    post_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific post"""
    post = await post_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Get user info and create PostWithUser
    from app.services.user_service import user_service
    from app.models.user import UserSearch
    
    user = await user_service.get_user_by_id(post.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Post author not found")
    
    user_search = UserSearch(
        user_id=user.user_id,
        username=user.username,
        avatar_url=user.avatar_url,
        bio=user.bio,
        followers_count=user.followers_count
    )
    
    return PostWithUser(**post.dict(), user=user_search)


@router.put("/{post_id}", response_model=Post)
async def update_post(
    post_id: str,
    post_data: PostUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update a post (only by owner)"""
    post = await post_service.update_post(post_id, current_user["user_id"], post_data)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found or not authorized")
    return post


@router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a post (only by owner)"""
    success = await post_service.delete_post(post_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="Post not found or not authorized")
    return {"message": "Post deleted successfully"}


@router.post("/{post_id}/like")
async def toggle_like_post(
    post_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Like or unlike a post"""
    # Check if post exists
    post = await post_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Import like service here to avoid circular imports
    from app.services.like_service import like_service
    
    # Check if already liked
    is_liked = await like_service.is_liked(post_id, current_user["user_id"])
    
    if is_liked:
        # Unlike
        success = await like_service.unlike_post(post_id, current_user["user_id"])
        return {"liked": False, "success": success}
    else:
        # Like
        success = await like_service.like_post(post_id, current_user["user_id"])
        return {"liked": True, "success": success}






@router.get("/{post_id}/comments", response_model=List[CommentWithUser])
async def get_post_comments(
    post_id: str,
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get comments for a post"""
    # Check if post exists
    post = await post_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    from app.services.comment_service import comment_service
    comments = await comment_service.get_post_comments(post_id, limit)
    return comments


@router.post("/{post_id}/comments", response_model=Comment)
async def create_comment(
    post_id: str,
    comment_data: CommentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add a comment to a post"""
    # Check if post exists
    post = await post_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    from app.services.comment_service import comment_service
    comment = await comment_service.create_comment(post_id, comment_data, current_user["user_id"])
    return comment


@router.delete("/{post_id}/comments/{comment_id}")
async def delete_comment(
    post_id: str,
    comment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a comment (only by owner)"""
    from app.services.comment_service import comment_service
    success = await comment_service.delete_comment(post_id, comment_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="Comment not found or not authorized")
    return {"message": "Comment deleted successfully"}