from pydantic import BaseModel
from datetime import datetime


class Like(BaseModel):
    post_id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True