from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from .user import UserSearch


class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class CommentCreate(CommentBase):
    pass


class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=1000)


class Comment(CommentBase):
    comment_id: str
    post_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommentWithUser(Comment):
    user: UserSearch