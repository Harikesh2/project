from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, ClassVar
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# DynamoDB single-table key helpers (SocialMedia table)
# ---------------------------------------------------------------------------

class NotificationEntityKeys:
    """PK/SK builders for notification entities."""

    NOTIFICATION_PK_PREFIX: ClassVar[str] = "NOTIFICATION#"
    METADATA_SK: ClassVar[str] = "METADATA"

    @staticmethod
    def pk(notification_id: str) -> str:
        return f"NOTIFICATION#{notification_id}"

    @staticmethod
    def metadata_key(notification_id: str) -> dict[str, str]:
        return {"Pk": NotificationEntityKeys.pk(notification_id), "Sk": NotificationEntityKeys.METADATA_SK}

    @staticmethod
    def user_notification_sk(created_at: str, notification_id: str) -> str:
        return f"NOTIFICATION#{created_at}#{notification_id}"

    @staticmethod
    def user_notification_key(recipient_id: str, created_at: str, notification_id: str) -> dict[str, str]:
        return {
            "Pk": f"USER#{recipient_id}",
            "Sk": NotificationEntityKeys.user_notification_sk(created_at, notification_id),
        }


# ---------------------------------------------------------------------------
# DynamoDB item models
# ---------------------------------------------------------------------------

class NotificationRecord(BaseModel):
    """Canonical notification at PK=NOTIFICATION#{id}, SK=METADATA."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(default=NotificationEntityKeys.METADATA_SK, alias="Sk")
    notification_id: str
    recipient_id: str
    actor_id: str
    type: str  # "like" | "follow" | "comment"
    entity_id: str
    entity_type: str  # "post" | "user" | "comment"
    payload: dict
    read_at: Optional[str] = None
    created_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "NotificationRecord":
        return cls.model_validate(item)

    @classmethod
    def create(
        cls,
        notification_id: str,
        recipient_id: str,
        actor_id: str,
        type_: str,
        entity_id: str,
        entity_type: str,
        payload: dict,
        created_at: str,
    ) -> "NotificationRecord":
        return cls(
            Pk=NotificationEntityKeys.pk(notification_id),
            Sk=NotificationEntityKeys.METADATA_SK,
            notification_id=notification_id,
            recipient_id=recipient_id,
            actor_id=actor_id,
            type=type_,
            entity_id=entity_id,
            entity_type=entity_type,
            payload=payload,
            created_at=created_at,
        )


class UserNotificationRecord(BaseModel):
    """User notification list item at PK=USER#{recipient}, SK=NOTIFICATION#{created_at}#{id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    notification_id: str
    recipient_id: str
    actor_id: str
    type: str
    entity_id: str
    entity_type: str
    payload: dict
    read_at: Optional[str] = None
    created_at: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "UserNotificationRecord":
        return cls.model_validate(item)

    @classmethod
    def from_canonical(cls, canonical: NotificationRecord) -> "UserNotificationRecord":
        return cls(
            Pk=f"USER#{canonical.recipient_id}",
            Sk=NotificationEntityKeys.user_notification_sk(canonical.created_at, canonical.notification_id),
            notification_id=canonical.notification_id,
            recipient_id=canonical.recipient_id,
            actor_id=canonical.actor_id,
            type=canonical.type,
            entity_id=canonical.entity_id,
            entity_type=canonical.entity_type,
            payload=canonical.payload,
            read_at=canonical.read_at,
            created_at=canonical.created_at,
        )


def record_to_notification(item: dict) -> "Notification":
    """Map a notification DynamoDB item to the API Notification model."""
    return Notification(
        notification_id=item["notification_id"],
        recipient_id=item["recipient_id"],
        actor_id=item["actor_id"],
        type=item["type"],
        entity_id=item["entity_id"],
        entity_type=item["entity_type"],
        payload=item.get("payload", {}),
        read_at=item.get("read_at"),
        created_at=item["created_at"],
    )


# ---------------------------------------------------------------------------
# API request / response models (public contract)
# ---------------------------------------------------------------------------

class NotificationType(str, Enum):
    LIKE = "like"
    FOLLOW = "follow"
    COMMENT = "comment"


class Notification(BaseModel):
    notification_id: str
    recipient_id: str
    actor_id: str
    type: NotificationType
    entity_id: str
    entity_type: str
    payload: dict
    read_at: Optional[datetime] = None
    created_at: datetime

    @field_validator("created_at", "read_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[Notification]
    next_token: Optional[str] = None


class UnreadCountResponse(BaseModel):
    count: int
