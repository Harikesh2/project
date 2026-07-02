from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, ClassVar
from datetime import datetime
from .user import UserSearch


# ---------------------------------------------------------------------------
# DynamoDB single-table key helpers (SocialMedia table)
# ---------------------------------------------------------------------------

class PostEntityKeys:
    """PK/SK and GSI key builders for post entities."""

    METADATA_SK: ClassVar[str] = "METADATA"
    GSI3_PK: ClassVar[str] = "POSTS"
    GSI3_INDEX: ClassVar[str] = "GSI3-global-feed-index"
    POST_PK_PREFIX: ClassVar[str] = "POST#"

    @staticmethod
    def post_pk(post_id: str) -> str:
        return f"POST#{post_id}"

    @staticmethod
    def metadata_key(post_id: str) -> dict[str, str]:
        return {"Pk": PostEntityKeys.post_pk(post_id), "Sk": PostEntityKeys.METADATA_SK}

    @staticmethod
    def timeline_sk(post_id: str) -> str:
        return f"POST#{post_id}"

    @staticmethod
    def timeline_key(user_id: str, post_id: str) -> dict[str, str]:
        return {"Pk": f"USER#{user_id}", "Sk": PostEntityKeys.timeline_sk(post_id)}

    @staticmethod
    def gsi3_keys(created_at: str) -> tuple[str, str]:
        return PostEntityKeys.GSI3_PK, created_at


# ---------------------------------------------------------------------------
# DynamoDB item models
# ---------------------------------------------------------------------------

class PostMetadataRecord(BaseModel):
    """Canonical post at PK=POST#{id}, SK=METADATA."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(default=PostEntityKeys.METADATA_SK, alias="Sk")
    gsi3pk: str = Field(alias="GSI3PK")
    gsi3sk: str = Field(alias="GSI3SK")
    post_id: str
    user_id: str
    content: str
    image_url: Optional[str] = None
    created_at: str
    updated_at: str
    likes_count: int = 0
    comments_count: int = 0

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "PostMetadataRecord":
        data = dict(item)
        if "GSI3PK" not in data and data.get("created_at"):
            gsi3_pk, gsi3_sk = PostEntityKeys.gsi3_keys(data["created_at"])
            data["GSI3PK"] = gsi3_pk
            data["GSI3SK"] = gsi3_sk
        return cls.model_validate(data)

    @classmethod
    def from_timeline_item(cls, item: dict) -> "PostMetadataRecord":
        """Build canonical METADATA from a legacy timeline-only item."""
        created_at = item["created_at"]
        gsi3_pk, gsi3_sk = PostEntityKeys.gsi3_keys(created_at)
        return cls(
            Pk=PostEntityKeys.post_pk(item["post_id"]),
            Sk=PostEntityKeys.METADATA_SK,
            GSI3PK=gsi3_pk,
            GSI3SK=gsi3_sk,
            post_id=item["post_id"],
            user_id=item["user_id"],
            content=item["content"],
            image_url=item.get("image_url"),
            created_at=created_at,
            updated_at=item.get("updated_at", created_at),
            likes_count=int(item.get("likes_count", 0)),
            comments_count=int(item.get("comments_count", 0)),
        )

    @classmethod
    def from_create(
        cls, post_data: "PostCreate", post_id: str, user_id: str, now: str
    ) -> "PostMetadataRecord":
        gsi3_pk, gsi3_sk = PostEntityKeys.gsi3_keys(now)
        return cls(
            Pk=PostEntityKeys.post_pk(post_id),
            Sk=PostEntityKeys.METADATA_SK,
            GSI3PK=gsi3_pk,
            GSI3SK=gsi3_sk,
            post_id=post_id,
            user_id=user_id,
            content=post_data.content,
            image_url=post_data.image_url,
            created_at=now,
            updated_at=now,
        )


class UserTimelinePostRecord(BaseModel):
    """Timeline duplicate at PK=USER#{user_id}, SK=POST#{post_id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    post_id: str
    user_id: str
    content: str
    image_url: Optional[str] = None
    created_at: str
    updated_at: str
    likes_count: int = 0
    comments_count: int = 0

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "UserTimelinePostRecord":
        return cls.model_validate(item)

    @classmethod
    def from_metadata(cls, metadata: PostMetadataRecord) -> "UserTimelinePostRecord":
        return cls(
            Pk=f"USER#{metadata.user_id}",
            Sk=f"POST#{metadata.post_id}",
            post_id=metadata.post_id,
            user_id=metadata.user_id,
            content=metadata.content,
            image_url=metadata.image_url,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            likes_count=metadata.likes_count,
            comments_count=metadata.comments_count,
        )


def record_to_post(item: dict) -> "Post":
    """Map a METADATA or timeline DynamoDB item to the API Post model."""
    def _int(value, default: int = 0) -> int:
        return int(value) if value is not None else default

    return Post(
        post_id=item["post_id"],
        user_id=item["user_id"],
        content=item["content"],
        image_url=item.get("image_url"),
        created_at=item["created_at"],
        updated_at=item.get("updated_at", item["created_at"]),
        likes_count=_int(item.get("likes_count")),
        comments_count=_int(item.get("comments_count")),
    )


def is_legacy_timeline_post(item: dict) -> bool:
    """True when post exists only on the user timeline partition (pre-migration)."""
    pk = item.get("Pk", "")
    sk = item.get("Sk", "")
    return pk.startswith("USER#") and sk.startswith("POST#")


# ---------------------------------------------------------------------------
# API request / response models (public contract — unchanged for clients)
# ---------------------------------------------------------------------------

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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class PostWithUser(Post):
    user: UserSearch
    is_liked: Optional[bool] = None

    @classmethod
    def from_post_and_user(cls, post: Post, user: UserSearch, is_liked: Optional[bool] = None) -> "PostWithUser":
        return cls(**post.model_dump(), user=user, is_liked=is_liked)
