import logging
import uuid
from datetime import datetime
from typing import Optional

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from pydantic import ValidationError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.chat import (
    build_conversation_id,
    ChatEntityKeys,
    ConversationMetadataRecord,
    ChatMessageRecord,
    UserInboxRecord,
    Conversation,
    ConversationWithUser,
    ChatMessage,
    ConversationPage,
    MessagePage,
    ChatUnreadCountResponse,
    encode_cursor,
    decode_cursor,
    SelfChatError,
    RecipientNotFoundError,
    ConversationNotFoundError,
    NotParticipantError,
    InvalidCursorError,
    ContentValidationError,
)
from app.models.user import UserSearch
from app.services.user_service import user_service

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self):
        self.table_name = settings.social_media_table
        self.max_message_length = settings.chat_max_message_length

    def _validate_content(self, content: str) -> str:
        """Validate and return trimmed message content."""
        stripped = content.strip() if content else ""
        if not stripped:
            raise ContentValidationError("Message content cannot be blank")
        if len(stripped) > self.max_message_length:
            raise ContentValidationError(
                f"Message content exceeds {self.max_message_length} characters"
            )
        return stripped

    async def _get_metadata(self, conversation_id: str) -> Optional[ConversationMetadataRecord]:
        """Fetch conversation metadata without membership checks."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            response = await table.get_item(
                Key=ChatEntityKeys.conversation_metadata_key(conversation_id)
            )
            if "Item" not in response:
                return None
            return ConversationMetadataRecord.from_dynamo_item(response["Item"])

    async def _find_message_by_client_id(
        self, conversation_id: str, client_message_id: str
    ) -> Optional[ChatMessageRecord]:
        """Locate an existing message by its client idempotency key.

        DynamoDB filter expressions are applied after the Limit, so this helper
        paginates through the conversation partition until a match is found or
        the partition is exhausted.
        """
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            last_key = None
            while True:
                kwargs = {
                    "KeyConditionExpression": Key("Pk").eq(
                        ChatEntityKeys.conversation_pk(conversation_id)
                    )
                    & Key("Sk").begins_with("MESSAGE#"),
                    "FilterExpression": Attr("client_message_id").eq(client_message_id),
                }
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                response = await table.query(**kwargs)
                if response["Items"]:
                    return ChatMessageRecord.from_dynamo_item(response["Items"][0])
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    return None

    async def _get_inbox_unread(
        self, user_id: str, updated_at: str, conversation_id: str
    ) -> int:
        """Read the current unread_count for a user's inbox row (0 if missing)."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            response = await table.get_item(
                Key=ChatEntityKeys.inbox_key(user_id, updated_at, conversation_id),
                ProjectionExpression="unread_count",
            )
            item = response.get("Item")
            return int(item.get("unread_count", 0)) if item else 0

    async def _mark_conversation_read(
        self, user_id: str, conversation_id: str
    ) -> None:
        """Zero a single user's unread count for a conversation."""
        metadata = await self._get_metadata(conversation_id)
        if metadata is None:
            return
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            key = ChatEntityKeys.inbox_key(user_id, metadata.updated_at, conversation_id)
            await table.update_item(
                Key=key,
                UpdateExpression="SET unread_count = :zero",
                ExpressionAttributeValues={":zero": 0},
            )

    async def get_unread_count(self, user_id: str) -> ChatUnreadCountResponse:
        """Total unread messages across all of a user's conversations."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            total = 0
            last_key = None
            kwargs = {
                "KeyConditionExpression": Key("Pk").eq(f"USER#{user_id}")
                & Key("Sk").begins_with("CHAT#"),
                "ProjectionExpression": "unread_count",
            }
            while True:
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                response = await table.query(**kwargs)
                total += sum(
                    item.get("unread_count", 0)
                    for item in response.get("Items", [])
                )
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
            return ChatUnreadCountResponse(count=total)

    async def get_or_create_direct_conversation(
        self, current_user_id: str, recipient_id: str
    ) -> Conversation:
        if current_user_id == recipient_id:
            raise SelfChatError("Cannot create a conversation with yourself")

        recipient = await user_service.get_user_by_id(recipient_id)
        if not recipient:
            raise RecipientNotFoundError("Recipient not found")
        current_user = await user_service.get_user_by_id(current_user_id)

        conversation_id = build_conversation_id(current_user_id, recipient_id)

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            response = await table.get_item(
                Key=ChatEntityKeys.conversation_metadata_key(conversation_id)
            )
            if "Item" in response:
                return Conversation.from_metadata(
                    ConversationMetadataRecord.from_dynamo_item(response["Item"])
                )

            now = datetime.utcnow().isoformat()
            participant_ids = sorted([current_user_id, recipient_id])

            metadata = ConversationMetadataRecord.create(
                conversation_id=conversation_id,
                participant_ids=participant_ids,
                created_at=now,
                updated_at=now,
            )

            self_card = UserSearch.from_user(current_user) if current_user else UserSearch(user_id=current_user_id, username="Unknown", avatar_url=None)
            other_card = UserSearch.from_user(recipient)

            inbox_self = UserInboxRecord.create(
                user_id=current_user_id,
                other_user=other_card,
                preview="",
                updated_at=now,
                conversation_id=conversation_id,
                participant_ids=participant_ids,
                created_at=now,
            )

            inbox_other = UserInboxRecord.create(
                user_id=recipient_id,
                other_user=self_card,
                preview="",
                updated_at=now,
                conversation_id=conversation_id,
                participant_ids=participant_ids,
                created_at=now,
            )

            try:
                client = dynamodb.meta.client
                await client.transact_write_items(
                    TransactItems=[
                        {
                            "Put": {
                                "TableName": self.table_name,
                                "Item": metadata.to_dynamo_item(),
                                "ConditionExpression": "attribute_not_exists(Sk)",
                            }
                        },
                        {
                            "Put": {
                                "TableName": self.table_name,
                                "Item": inbox_self.to_dynamo_item(),
                            }
                        },
                        {
                            "Put": {
                                "TableName": self.table_name,
                                "Item": inbox_other.to_dynamo_item(),
                            }
                        },
                    ]
                )
                return Conversation.from_metadata(metadata)

            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code == "TransactionCanceledException":
                    response = await table.get_item(
                        Key=ChatEntityKeys.conversation_metadata_key(conversation_id)
                    )
                    if "Item" in response:
                        return Conversation.from_metadata(
                            ConversationMetadataRecord.from_dynamo_item(response["Item"])
                        )
                raise

    async def list_conversations(
        self, user_id: str, limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> ConversationPage:
        limit = limit or settings.chat_default_conversation_limit
        limit = min(limit, settings.chat_max_conversation_limit)

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            kwargs = {
                "KeyConditionExpression": Key("Pk").eq(f"USER#{user_id}")
                & Key("Sk").begins_with("CHAT#"),
                "ScanIndexForward": False,
                "Limit": limit,
            }

            if cursor:
                try:
                    kwargs["ExclusiveStartKey"] = decode_cursor(cursor)
                except ValueError as exc:
                    raise InvalidCursorError("Invalid cursor") from exc

            response = await table.query(**kwargs)

            inbox_records = []
            for item in response.get("Items", []):
                try:
                    inbox_records.append(UserInboxRecord.from_dynamo_item(item))
                except ValidationError:
                    # Stale rows from the pre-refactor schema are dropped so
                    # one bad row can't break the whole list. They are rebuilt
                    # on the next message send.
                    logger.warning("Skipping stale inbox row: %s", item.get("Sk"))

            items = [
                ConversationWithUser.from_inbox_record(record)
                for record in inbox_records
            ]

            next_cursor = None
            if "LastEvaluatedKey" in response:
                next_cursor = encode_cursor(response["LastEvaluatedKey"])

            return ConversationPage(items=list(items), next_cursor=next_cursor)

    async def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> MessagePage:
        metadata = await self.get_conversation_for_member(conversation_id, user_id)
        if metadata is None:
            raise ConversationNotFoundError("Conversation not found")

        limit = limit or settings.chat_default_message_limit
        limit = min(limit, settings.chat_max_message_limit)

        # Opening the conversation clears its unread badge.
        await self._mark_conversation_read(user_id, conversation_id)

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            kwargs = {
                "KeyConditionExpression": Key("Pk").eq(
                    ChatEntityKeys.conversation_pk(conversation_id)
                )
                & Key("Sk").begins_with("MESSAGE#"),
                # Return newest messages first so the first page is useful for
                # chat UIs; older pages are fetched with the returned cursor.
                "ScanIndexForward": False,
                "Limit": limit,
            }

            if cursor:
                try:
                    kwargs["ExclusiveStartKey"] = decode_cursor(cursor)
                except ValueError as exc:
                    raise InvalidCursorError("Invalid cursor") from exc

            response = await table.query(**kwargs)

            messages = [
                ChatMessage.from_record(ChatMessageRecord.from_dynamo_item(item))
                for item in response.get("Items", [])
            ]

            next_cursor = None
            if "LastEvaluatedKey" in response:
                next_cursor = encode_cursor(response["LastEvaluatedKey"])

            return MessagePage(items=messages, next_cursor=next_cursor)

    async def send_message(
        self,
        conversation_id: str,
        sender_id: str,
        content: str,
        client_message_id: str,
    ) -> ChatMessage:
        metadata = await self.get_conversation_for_member(conversation_id, sender_id)
        if metadata is None:
            raise ConversationNotFoundError("Conversation not found")

        trimmed = self._validate_content(content)

        # Idempotency: if the client retries a send, return the persisted message.
        existing = await self._find_message_by_client_id(conversation_id, client_message_id)
        if existing:
            return ChatMessage.from_record(existing)

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            now = datetime.utcnow().isoformat()
            message_id = str(uuid.uuid4())
            other_user_id = [p for p in metadata.participant_ids if p != sender_id][0]

            sender = await user_service.get_user_by_id(sender_id)
            other_user = await user_service.get_user_by_id(other_user_id)
            sender_card = UserSearch.from_user(sender) if sender else UserSearch(user_id=sender_id, username="Unknown", avatar_url=None)
            other_card = UserSearch.from_user(other_user) if other_user else UserSearch(user_id=other_user_id, username="Unknown", avatar_url=None)

            recipient_unread = await self._get_inbox_unread(
                other_user_id, metadata.updated_at, conversation_id
            )
            recipient_unread += 1

            message = ChatMessageRecord.create(
                conversation_id=conversation_id,
                message_id=message_id,
                sender_id=sender_id,
                content=trimmed,
                created_at=now,
                client_message_id=client_message_id,
            )

            old_inbox_self_key = ChatEntityKeys.inbox_key(
                sender_id, metadata.updated_at, conversation_id
            )
            old_inbox_other_key = ChatEntityKeys.inbox_key(
                other_user_id, metadata.updated_at, conversation_id
            )

            new_inbox_self = UserInboxRecord.create(
                user_id=sender_id,
                other_user=other_card,
                preview=trimmed,
                updated_at=now,
                conversation_id=conversation_id,
                participant_ids=metadata.participant_ids,
                created_at=metadata.created_at,
                last_message_at=now,
            )
            new_inbox_other = UserInboxRecord.create(
                user_id=other_user_id,
                other_user=sender_card,
                preview=trimmed,
                updated_at=now,
                conversation_id=conversation_id,
                participant_ids=metadata.participant_ids,
                created_at=metadata.created_at,
                last_message_at=now,
                unread_count=recipient_unread,
            )

            try:
                client = dynamodb.meta.client
                await client.transact_write_items(
                    TransactItems=[
                        {
                            "Put": {
                                "TableName": self.table_name,
                                "Item": message.to_dynamo_item(),
                            }
                        },
                        {
                            # Conditional idempotency guard keyed by the client
                            # message id. A retry with the same client id will
                            # fail this condition and fall through to the read
                            # below instead of creating a duplicate.
                            "Put": {
                                "TableName": self.table_name,
                                "Item": {
                                    "Pk": ChatEntityKeys.conversation_pk(conversation_id),
                                    "Sk": f"CLIENT_MESSAGE#{client_message_id}",
                                    "message_id": message_id,
                                    "created_at": now,
                                },
                                "ConditionExpression": "attribute_not_exists(Sk)",
                            }
                        },
                        {
                            "Update": {
                                "TableName": self.table_name,
                                "Key": ChatEntityKeys.conversation_metadata_key(conversation_id),
                                "UpdateExpression": "SET last_message_preview = :preview, last_message_at = :now, updated_at = :new_updated_at",
                                "ConditionExpression": "updated_at = :old_updated_at",
                                "ExpressionAttributeValues": {
                                    ":preview": trimmed,
                                    ":now": now,
                                    ":new_updated_at": now,
                                    ":old_updated_at": metadata.updated_at,
                                },
                            }
                        },
                        {
                            "Delete": {
                                "TableName": self.table_name,
                                "Key": old_inbox_self_key,
                            }
                        },
                        {
                            "Delete": {
                                "TableName": self.table_name,
                                "Key": old_inbox_other_key,
                            }
                        },
                        {
                            "Put": {
                                "TableName": self.table_name,
                                "Item": new_inbox_self.to_dynamo_item(),
                            }
                        },
                        {
                            "Put": {
                                "TableName": self.table_name,
                                "Item": new_inbox_other.to_dynamo_item(),
                            }
                        },
                    ]
                )
                return ChatMessage.from_record(message)

            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code == "TransactionCanceledException":
                    existing = await self._find_message_by_client_id(
                        conversation_id, client_message_id
                    )
                    if existing:
                        return ChatMessage.from_record(existing)
                raise

    async def get_conversation_for_member(
        self, conversation_id: str, user_id: str
    ) -> Optional[ConversationMetadataRecord]:
        metadata = await self._get_metadata(conversation_id)
        if metadata is None:
            raise ConversationNotFoundError("Conversation not found")

        if user_id not in metadata.participant_ids:
            raise NotParticipantError("User is not a participant in this conversation")

        return metadata


chat_service = ChatService()
