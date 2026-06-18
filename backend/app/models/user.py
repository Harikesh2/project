from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)


class User(UserBase):
    user_id: str
    created_at: datetime
    updated_at: datetime
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0

    class Config:
        from_attributes = True


class UserProfile(User):
    is_following: Optional[bool] = None  # Whether current user follows this user
    is_followed_by: Optional[bool] = None  # Whether this user follows current user


class UserSearch(BaseModel):
    user_id: str
    username: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    followers_count: int = 0