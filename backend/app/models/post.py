from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .user import UserSearch


class PostBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    image_url: Optional[str] = None


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    image_url: Optional[str] = None


class Post(PostBase):
    post_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    comments_count: int = 0

    class Config:
        from_attributes = True


class PostWithUser(Post):
    user: UserSearch
    is_liked: Optional[bool] = None  # Whether current user liked this post