from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, ClassVar
from datetime import datetime


# ---------------------------------------------------------------------------
# DynamoDB single-table key helpers (SocialMedia table)
# ---------------------------------------------------------------------------

class UserEntityKeys:
    """PK/SK and GSI key builders for user entities."""

    METADATA_SK: ClassVar[str] = "METADATA"
    PROFILE_SK: ClassVar[str] = "PROFILE"
    SETTINGS_SK: ClassVar[str] = "SETTINGS"

    GSI1_SK: ClassVar[str] = "USER"
    GSI2_SK: ClassVar[str] = "USER"

    GSI1_INDEX: ClassVar[str] = "GSI1-email-index"
    GSI2_INDEX: ClassVar[str] = "GSI2-username-index"
    USER_PK_PREFIX: ClassVar[str] = "USER#"

    @staticmethod
    def pk(user_id: str) -> str:
        return f"USER#{user_id}"

    @staticmethod
    def metadata_key(user_id: str) -> dict[str, str]:
        return {"Pk": UserEntityKeys.pk(user_id), "Sk": UserEntityKeys.METADATA_SK}

    @staticmethod
    def profile_key(user_id: str) -> dict[str, str]:
        return {"Pk": UserEntityKeys.pk(user_id), "Sk": UserEntityKeys.PROFILE_SK}

    @staticmethod
    def gsi1_keys(email: str) -> tuple[str, str]:
        return f"EMAIL#{email.lower()}", UserEntityKeys.GSI1_SK

    @staticmethod
    def gsi2_keys(username: str) -> tuple[str, str]:
        return f"USERNAME#{username.lower()}", UserEntityKeys.GSI2_SK


# ---------------------------------------------------------------------------
# DynamoDB item models
# ---------------------------------------------------------------------------

class UserMetadataRecord(BaseModel):
    """Canonical user record stored at PK=USER#{id}, SK=METADATA."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(default=UserEntityKeys.METADATA_SK, alias="Sk")
    gsi1pk: str = Field(alias="GSI1PK")
    gsi1sk: str = Field(default=UserEntityKeys.GSI1_SK, alias="GSI1SK")
    gsi2pk: str = Field(alias="GSI2PK")
    gsi2sk: str = Field(default=UserEntityKeys.GSI2_SK, alias="GSI2SK")
    user_id: str
    username: str
    email: str
    password_hash: Optional[str] = None
    created_at: str
    updated_at: str
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "UserMetadataRecord":
        data = dict(item)
        # Backfill GSI keys for records written before single-table migration.
        if "GSI1PK" not in data and data.get("email"):
            gsi1_pk, gsi1_sk = UserEntityKeys.gsi1_keys(data["email"])
            data["GSI1PK"] = gsi1_pk
            data["GSI1SK"] = gsi1_sk
        if "GSI2PK" not in data and data.get("username"):
            gsi2_pk, gsi2_sk = UserEntityKeys.gsi2_keys(data["username"])
            data["GSI2PK"] = gsi2_pk
            data["GSI2SK"] = gsi2_sk
        return cls.model_validate(data)

    @classmethod
    def from_create(cls, user_data: "UserCreate", user_id: str, now: str) -> "UserMetadataRecord":
        gsi1_pk, gsi1_sk = UserEntityKeys.gsi1_keys(user_data.email)
        gsi2_pk, gsi2_sk = UserEntityKeys.gsi2_keys(user_data.username)
        return cls(
            Pk=UserEntityKeys.pk(user_id),
            Sk=UserEntityKeys.METADATA_SK,
            GSI1PK=gsi1_pk,
            GSI1SK=gsi1_sk,
            GSI2PK=gsi2_pk,
            GSI2SK=gsi2_sk,
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            created_at=now,
            updated_at=now,
        )


class UserProfileItem(BaseModel):
    """Optional profile fields stored at PK=USER#{id}, SK=PROFILE."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(default=UserEntityKeys.PROFILE_SK, alias="Sk")
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    updated_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "UserProfileItem":
        return cls.model_validate(item)

    @classmethod
    def from_create(cls, user_data: "UserCreate", user_id: str, now: str) -> "UserProfileItem":
        return cls(
            Pk=UserEntityKeys.pk(user_id),
            Sk=UserEntityKeys.PROFILE_SK,
            avatar_url=user_data.avatar_url,
            bio=user_data.bio,
            updated_at=now,
        )


def merge_user_records(
    metadata: UserMetadataRecord,
    profile: Optional[UserProfileItem] = None,
) -> "User":
    """Combine METADATA and PROFILE DynamoDB items into the public User model."""
    return User(
        user_id=metadata.user_id,
        username=metadata.username,
        email=metadata.email,
        avatar_url=profile.avatar_url if profile else None,
        bio=profile.bio if profile else None,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
        followers_count=metadata.followers_count,
        following_count=metadata.following_count,
        posts_count=metadata.posts_count,
    )


# ---------------------------------------------------------------------------
# API request / response models (public contract — unchanged for clients)
# ---------------------------------------------------------------------------

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

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class UserProfile(User):
    is_following: Optional[bool] = None
    is_followed_by: Optional[bool] = None


class UserSearch(BaseModel):
    user_id: str
    username: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    followers_count: int = 0

    @classmethod
    def from_user(cls, user: User) -> "UserSearch":
        return cls(
            user_id=user.user_id,
            username=user.username,
            avatar_url=user.avatar_url,
            bio=user.bio,
            followers_count=user.followers_count,
        )
