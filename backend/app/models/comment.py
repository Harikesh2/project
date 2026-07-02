from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, ClassVar
from datetime import datetime
from .user import UserSearch


# ---------------------------------------------------------------------------
# DynamoDB single-table key helpers (SocialMedia table)
# ---------------------------------------------------------------------------

class CommentEntityKeys:
    """PK/SK builders for comment entities."""

    COMMENT_PREFIX: ClassVar[str] = "COMMENT#"

    @staticmethod
    def comment_sk(comment_id: str) -> str:
        return f"{CommentEntityKeys.COMMENT_PREFIX}{comment_id}"

    @staticmethod
    def post_comment_key(post_id: str, comment_id: str) -> dict[str, str]:
        return {
            "Pk": f"POST#{post_id}",
            "Sk": CommentEntityKeys.comment_sk(comment_id),
        }

    @staticmethod
    def user_comment_key(user_id: str, comment_id: str) -> dict[str, str]:
        return {
            "Pk": f"USER#{user_id}",
            "Sk": CommentEntityKeys.comment_sk(comment_id),
        }


# ---------------------------------------------------------------------------
# DynamoDB item models
# ---------------------------------------------------------------------------

class PostCommentRecord(BaseModel):
    """Canonical comment: PK=POST#{post_id}, SK=COMMENT#{comment_id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    comment_id: str
    post_id: str
    user_id: str
    content: str
    created_at: str
    updated_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "PostCommentRecord":
        return cls.model_validate(item)

    @classmethod
    def from_create(
        cls, post_id: str, comment_data: "CommentCreate", user_id: str, comment_id: str, now: str
    ) -> "PostCommentRecord":
        return cls(
            Pk=f"POST#{post_id}",
            Sk=CommentEntityKeys.comment_sk(comment_id),
            comment_id=comment_id,
            post_id=post_id,
            user_id=user_id,
            content=comment_data.content,
            created_at=now,
            updated_at=now,
        )


class UserCommentRecord(BaseModel):
    """User activity duplicate: PK=USER#{user_id}, SK=COMMENT#{comment_id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    comment_id: str
    post_id: str
    user_id: str
    content: str
    created_at: str
    updated_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "UserCommentRecord":
        return cls.model_validate(item)

    @classmethod
    def from_post_comment(cls, canonical: PostCommentRecord) -> "UserCommentRecord":
        return cls(
            Pk=f"USER#{canonical.user_id}",
            Sk=CommentEntityKeys.comment_sk(canonical.comment_id),
            comment_id=canonical.comment_id,
            post_id=canonical.post_id,
            user_id=canonical.user_id,
            content=canonical.content,
            created_at=canonical.created_at,
            updated_at=canonical.updated_at,
        )


def record_to_comment(item: dict) -> "Comment":
    """Map a COMMENT DynamoDB item to the API Comment model."""
    return Comment(
        comment_id=item["comment_id"],
        post_id=item["post_id"],
        user_id=item["user_id"],
        content=item["content"],
        created_at=item["created_at"],
        updated_at=item.get("updated_at", item["created_at"]),
    )


# ---------------------------------------------------------------------------
# API request / response models (public contract — unchanged for clients)
# ---------------------------------------------------------------------------

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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class CommentWithUser(Comment):
    user: UserSearch

    @classmethod
    def from_comment_and_user(cls, comment: Comment, user: UserSearch) -> "CommentWithUser":
        return cls(**comment.model_dump(), user=user)
