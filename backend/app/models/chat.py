import hashlib
import json
from base64 import b64decode, b64encode
from typing import ClassVar, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.user import UserSearch


# ---------------------------------------------------------------------------
# DynamoDB single-table key helpers (SocialMedia table)
# ---------------------------------------------------------------------------

def build_conversation_id(user1: str, user2: str) -> str:
    """Derive a stable opaque ID from the two sorted user IDs.

    Returns a bare 64-char SHA-256 hex digest. The previous implementation
    prefixed the digest with ``"DM#"`` (e.g. ``"DM#a3f2..."``), which broke
    frontend URL routing — the browser treats ``#`` as a fragment separator
    and strips everything after it before sending the request, so the backend
    received only the ``"DM"`` half and raised ConversationNotFoundError.
    See project-changes.md Phase 11.
    """
    sorted_users = sorted([user1, user2])
    raw_str = f"{sorted_users[0]}:{sorted_users[1]}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


class ChatEntityKeys:
    """PK/SK builders for chat entities."""

    METADATA_SK: ClassVar[str] = "METADATA"

    @staticmethod
    def conversation_pk(conversation_id: str) -> str:
        return f"CHAT#{conversation_id}"

    @staticmethod
    def conversation_metadata_key(conversation_id: str) -> dict[str, str]:
        return {
            "Pk": ChatEntityKeys.conversation_pk(conversation_id),
            "Sk": ChatEntityKeys.METADATA_SK
        }

    @staticmethod
    def message_sk(created_at: str, message_id: str) -> str:
        return f"MESSAGE#{created_at}#{message_id}"

    @staticmethod
    def message_key(conversation_id: str, created_at: str, message_id: str) -> dict[str, str]:
        return {
            "Pk": ChatEntityKeys.conversation_pk(conversation_id),
            "Sk": ChatEntityKeys.message_sk(created_at, message_id)
        }

    @staticmethod
    def inbox_sk(updated_at: str, conversation_id: str) -> str:
        return f"CHAT#{updated_at}#{conversation_id}"

    @staticmethod
    def inbox_key(user_id: str, updated_at: str, conversation_id: str) -> dict[str, str]:
        return {
            "Pk": f"USER#{user_id}",
            "Sk": ChatEntityKeys.inbox_sk(updated_at, conversation_id)
        }


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def encode_cursor(key: dict) -> str:
    """Encode a DynamoDB LastEvaluatedKey as an opaque string."""
    return b64encode(json.dumps(key).encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> dict:
    """Decode an opaque cursor back to a DynamoDB ExclusiveStartKey.

    Raises ValueError for malformed cursors.
    """
    try:
        return json.loads(b64decode(cursor.encode("utf-8")).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid cursor") from exc


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class ChatError(Exception):
    """Base class for chat domain errors."""


class SelfChatError(ChatError):
    """Raised when a user tries to start a conversation with themselves."""


class RecipientNotFoundError(ChatError):
    """Raised when the target user does not exist."""


class ConversationNotFoundError(ChatError):
    """Raised when a conversation does not exist."""


class NotParticipantError(ChatError):
    """Raised when the caller is not a member of a conversation."""


class InvalidCursorError(ChatError):
    """Raised when a pagination cursor cannot be decoded."""


class ContentValidationError(ChatError):
    """Raised when message content is blank or over the length limit."""


# ---------------------------------------------------------------------------
# DynamoDB item models
# ---------------------------------------------------------------------------

class ConversationMetadataRecord(BaseModel):
    """Conversation metadata: PK=CHAT#{conversation_id}, SK=METADATA."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(default=ChatEntityKeys.METADATA_SK, alias="Sk")
    conversation_id: str
    participant_ids: list[str]
    created_at: str
    updated_at: str
    last_message_preview: Optional[str] = None
    last_message_at: Optional[str] = None

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "ConversationMetadataRecord":
        return cls.model_validate(item)

    @classmethod
    def create(
        cls,
        conversation_id: str,
        participant_ids: list[str],
        created_at: str,
        updated_at: str,
        last_message_preview: Optional[str] = None,
        last_message_at: Optional[str] = None,
    ) -> "ConversationMetadataRecord":
        return cls(
            Pk=ChatEntityKeys.conversation_pk(conversation_id),
            Sk=ChatEntityKeys.METADATA_SK,
            conversation_id=conversation_id,
            participant_ids=participant_ids,
            created_at=created_at,
            updated_at=updated_at,
            last_message_preview=last_message_preview,
            last_message_at=last_message_at,
        )


class ChatMessageRecord(BaseModel):
    """Message in a conversation: PK=CHAT#{conversation_id}, SK=MESSAGE#{created_at}#{message_id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    message_id: str
    sender_id: str
    content: str
    created_at: str
    client_message_id: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "ChatMessageRecord":
        return cls.model_validate(item)

    @classmethod
    def create(
        cls,
        conversation_id: str,
        message_id: str,
        sender_id: str,
        content: str,
        created_at: str,
        client_message_id: str,
    ) -> "ChatMessageRecord":
        return cls(
            Pk=ChatEntityKeys.conversation_pk(conversation_id),
            Sk=ChatEntityKeys.message_sk(created_at, message_id),
            message_id=message_id,
            sender_id=sender_id,
            content=content,
            created_at=created_at,
            client_message_id=client_message_id,
        )


class UserInboxRecord(BaseModel):
    """Inbox projection for a user: PK=USER#{user_id}, SK=CHAT#{updated_at}#{conversation_id}."""

    model_config = ConfigDict(populate_by_name=True)

    pk: str = Field(alias="Pk")
    sk: str = Field(alias="Sk")
    other_user_id: str
    preview: str
    updated_at: str
    conversation_id: str

    def to_dynamo_item(self) -> dict:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "UserInboxRecord":
        return cls.model_validate(item)

    @classmethod
    def create(
        cls,
        user_id: str,
        other_user_id: str,
        preview: str,
        updated_at: str,
        conversation_id: str,
    ) -> "UserInboxRecord":
        return cls(
            Pk=f"USER#{user_id}",
            Sk=ChatEntityKeys.inbox_sk(updated_at, conversation_id),
            other_user_id=other_user_id,
            preview=preview,
            updated_at=updated_at,
            conversation_id=conversation_id,
        )


# ---------------------------------------------------------------------------
# API response/request models
# ---------------------------------------------------------------------------

class Conversation(BaseModel):
    """Public REST representation of a direct conversation."""

    conversation_id: str
    participant_ids: list[str]
    created_at: str
    updated_at: str
    last_message_preview: Optional[str] = None
    last_message_at: Optional[str] = None

    @classmethod
    def from_metadata(cls, metadata: ConversationMetadataRecord) -> "Conversation":
        return cls(
            conversation_id=metadata.conversation_id,
            participant_ids=metadata.participant_ids,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            last_message_preview=metadata.last_message_preview,
            last_message_at=metadata.last_message_at,
        )


class ConversationWithUser(BaseModel):
    """Inbox row enriched with the other participant's public profile."""

    conversation_id: str
    participant_ids: list[str]
    created_at: str
    updated_at: str
    last_message_preview: Optional[str] = None
    last_message_at: Optional[str] = None
    other_user: UserSearch

    @classmethod
    def from_metadata_and_user(
        cls, metadata: ConversationMetadataRecord, other_user: UserSearch
    ) -> "ConversationWithUser":
        return cls(
            conversation_id=metadata.conversation_id,
            participant_ids=metadata.participant_ids,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            last_message_preview=metadata.last_message_preview,
            last_message_at=metadata.last_message_at,
            other_user=other_user,
        )


class ChatMessage(BaseModel):
    """Public REST/WebSocket representation of a chat message."""

    message_id: str
    sender_id: str
    content: str
    created_at: str
    client_message_id: str

    @classmethod
    def from_record(cls, record: ChatMessageRecord) -> "ChatMessage":
        return cls(
            message_id=record.message_id,
            sender_id=record.sender_id,
            content=record.content,
            created_at=record.created_at,
            client_message_id=record.client_message_id,
        )


class ConversationPage(BaseModel):
    """Paginated inbox response."""

    items: list[ConversationWithUser]
    next_cursor: Optional[str] = None


class MessagePage(BaseModel):
    """Paginated message history response."""

    items: list[ChatMessage]
    next_cursor: Optional[str] = None


# ---------------------------------------------------------------------------
# WebSocket event models
# ---------------------------------------------------------------------------

class IncomingMessageEvent(BaseModel):
    """Validated incoming WebSocket message.send event."""

    type: str
    conversation_id: str
    client_message_id: str
    content: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v != "message.send":
            raise ValueError(f"Unsupported event type: {v}")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message content cannot be blank")
        return stripped
