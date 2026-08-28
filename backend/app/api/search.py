from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.auth.clerk import get_current_user
from app.models.post import PostWithUser
from app.models.user import UserSearch
from app.services.embedding_service import embedding_service
from app.services.post_service import post_service
from app.services.user_service import user_service

router = APIRouter()


@router.get("/posts", response_model=List[PostWithUser])
async def search_posts(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not q.strip():
        posts = await post_service.get_global_feed(limit=limit)
    else:
        post_ids = embedding_service.search_posts(q, limit=limit)
        if not post_ids:
            posts = await post_service.get_global_feed(limit=limit)
        else:
            posts = await post_service.batch_get_posts(post_ids)

    results: List[PostWithUser] = []
    for post in posts:
        user = await user_service.get_user_by_id(post.user_id)
        user_search = UserSearch.from_user(user) if user else None
        if user_search:
            results.append(PostWithUser.from_post_and_user(post, user_search))
    return results


@router.get("/users", response_model=List[UserSearch])
async def search_users(
    q: str = Query("", description="Search query"),
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not q.strip():
        return await user_service.search_users("", limit)

    user_ids = embedding_service.search_users(q, limit=limit)
    if user_ids:
        users = await user_service.batch_get_users(user_ids)
        if users:
            return [UserSearch.from_user(u) for u in users]

    return await user_service.search_users(q, limit)
