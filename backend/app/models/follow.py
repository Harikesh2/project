from pydantic import BaseModel
from datetime import datetime
from .user import UserSearch


class Follow(BaseModel):
    follower_id: str
    following_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class FollowWithUser(Follow):
    user: UserSearch  # The user being followed or the follower