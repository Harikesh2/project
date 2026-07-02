from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import ClassVar
from datetime import datetime
from .user import UserSearch


# ---------------------------------------------------------------------------
# DynamoDB single-table key helpers (SocialMedia table)
# ---------------------------------------------------------------------------

class FollowEntityKeys:
    """PK/SK builders for follow relationship items."""

    FOLLOWING_PREFIX: ClassVar[str] = "FOLLOWING#"
    FOLLOWER_PREFIX: ClassVar[str] = "FOLLOWER#"

    @staticmethod
    def following_sk(target_user_id: str) -> str:
        return f"{FollowEntityKeys.FOLLOWING_PREFIX}{target_user_id}"

    @staticmethod
    def follower_sk(follower_id: str) -> str:
        return f"{FollowEntityKeys.FOLLOWER_PREFIX}{follower_id}"

    @staticmethod
    def following_key(follower_id: str, following_id: str) -> dict[str, str]:
        return {
            "Pk": f"USER#{follower_id}",
            "Sk": FollowEntityKeys.following_sk(following_id),
        }

    @staticmethod
    def follower_key(following_id: str, follower_id: str) -> dict[str, str]:
        return {
            "Pk": f"USER#{following_id}",
            "Sk": FollowEntityKeys.follower_sk(follower_id),
        }


# ---------------------------------------------------------------------------
# DynamoDB item models
# ---------------------------------------------------------------------------

class FollowingRecord(BaseModel):
    """Following edge: PK=USER#{follower}, SK=FOLLOWING#{target}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    follower_id: str
    following_id: str
    created_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "FollowingRecord":
        return cls.model_validate(item)

    @classmethod
    def create(cls, follower_id: str, following_id: str, created_at: str) -> "FollowingRecord":
        return cls(
            Pk=f"USER#{follower_id}",
            Sk=FollowEntityKeys.following_sk(following_id),
            follower_id=follower_id,
            following_id=following_id,
            created_at=created_at,
        )


class FollowerRecord(BaseModel):
    """Follower edge: PK=USER#{target}, SK=FOLLOWER#{follower}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    follower_id: str
    following_id: str
    created_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "FollowerRecord":
        return cls.model_validate(item)

    @classmethod
    def create(cls, follower_id: str, following_id: str, created_at: str) -> "FollowerRecord":
        return cls(
            Pk=f"USER#{following_id}",
            Sk=FollowEntityKeys.follower_sk(follower_id),
            follower_id=follower_id,
            following_id=following_id,
            created_at=created_at,
        )


def record_to_follow(item: dict) -> "Follow":
    """Map a FOLLOWING or FOLLOWER DynamoDB item to the API Follow model."""
    return Follow(
        follower_id=item["follower_id"],
        following_id=item["following_id"],
        created_at=item["created_at"],
    )


# ---------------------------------------------------------------------------
# API request / response models (public contract — unchanged for clients)
# ---------------------------------------------------------------------------

class Follow(BaseModel):
    follower_id: str
    following_id: str
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class FollowWithUser(Follow):
    user: UserSearch

    @classmethod
    def from_follow_and_user(cls, follow: Follow, user: UserSearch) -> "FollowWithUser":
        return cls(**follow.model_dump(), user=user)
