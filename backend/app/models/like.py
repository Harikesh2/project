from pydantic import BaseModel, field_validator, ConfigDict, Field
from typing import ClassVar
from datetime import datetime


# ---------------------------------------------------------------------------
# DynamoDB single-table key helpers (SocialMedia table)
# ---------------------------------------------------------------------------

class LikeEntityKeys:
    """PK/SK builders for like relationship items."""

    LIKE_PREFIX: ClassVar[str] = "LIKE#"

    @staticmethod
    def post_like_sk(user_id: str) -> str:
        return f"{LikeEntityKeys.LIKE_PREFIX}{user_id}"

    @staticmethod
    def user_like_sk(post_id: str) -> str:
        return f"{LikeEntityKeys.LIKE_PREFIX}{post_id}"

    @staticmethod
    def post_like_key(post_id: str, user_id: str) -> dict[str, str]:
        return {
            "Pk": f"POST#{post_id}",
            "Sk": LikeEntityKeys.post_like_sk(user_id),
        }

    @staticmethod
    def user_like_key(user_id: str, post_id: str) -> dict[str, str]:
        return {
            "Pk": f"USER#{user_id}",
            "Sk": LikeEntityKeys.user_like_sk(post_id),
        }


# ---------------------------------------------------------------------------
# DynamoDB item models
# ---------------------------------------------------------------------------

class PostLikeRecord(BaseModel):
    """Like on a post: PK=POST#{post_id}, SK=LIKE#{user_id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    post_id: str
    user_id: str
    created_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "PostLikeRecord":
        return cls.model_validate(item)

    @classmethod
    def create(cls, post_id: str, user_id: str, created_at: str) -> "PostLikeRecord":
        return cls(
            Pk=f"POST#{post_id}",
            Sk=LikeEntityKeys.post_like_sk(user_id),
            post_id=post_id,
            user_id=user_id,
            created_at=created_at,
        )


class UserLikeRecord(BaseModel):
    """Liked post by user: PK=USER#{user_id}, SK=LIKE#{post_id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    post_id: str
    user_id: str
    created_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "UserLikeRecord":
        return cls.model_validate(item)

    @classmethod
    def create(cls, post_id: str, user_id: str, created_at: str) -> "UserLikeRecord":
        return cls(
            Pk=f"USER#{user_id}",
            Sk=LikeEntityKeys.user_like_sk(post_id),
            post_id=post_id,
            user_id=user_id,
            created_at=created_at,
        )


def record_to_like(item: dict) -> "Like":
    """Map a LIKE DynamoDB item to the API Like model."""
    return Like(
        post_id=item["post_id"],
        user_id=item["user_id"],
        created_at=item["created_at"],
    )


# ---------------------------------------------------------------------------
# API response model (public contract — unchanged for clients)
# ---------------------------------------------------------------------------

class Like(BaseModel):
    post_id: str
    user_id: str
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    model_config = ConfigDict(from_attributes=True)
