import logging
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.notification import (
    Notification,
    NotificationRecord,
    UserNotificationRecord,
    NotificationEntityKeys,
    record_to_notification,
    UnreadCountResponse,
    NotificationListResponse,
)
from app.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self):
        self.table_name = settings.social_media_table

    async def create_notification(
        self,
        recipient_id: str,
        actor_id: str,
        type_: str,
        entity_id: str,
        entity_type: str,
        payload: dict,
    ) -> Optional[Notification]:
        """Create canonical + user list notification items and broadcast via WS."""
        if not recipient_id or not actor_id:
            return None

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            now = datetime.utcnow().isoformat()
            notification_id = str(uuid4())

            canonical = NotificationRecord.create(
                notification_id=notification_id,
                recipient_id=recipient_id,
                actor_id=actor_id,
                type_=type_,
                entity_id=entity_id,
                entity_type=entity_type,
                payload=payload,
                created_at=now,
            )
            user_item = UserNotificationRecord.from_canonical(canonical)

            try:
                await table.put_item(
                    Item=canonical.to_dynamo_item(),
                    ConditionExpression="attribute_not_exists(Sk)",
                )
                await table.put_item(Item=user_item.to_dynamo_item())

                notification = record_to_notification(canonical.to_dynamo_item())

                # Broadcast to recipient via WS if connected
                await connection_manager.send_to_users(
                    [recipient_id], {"type": "notification.created", "notification": notification.model_dump(mode="json")}
                )

                return notification

            except ClientError as e:
                logger.error(f"Error creating notification: {e}")
                return None

    async def get_user_notifications(
        self, user_id: str, limit: int = 20, next_token: Optional[str] = None
    ) -> NotificationListResponse:
        """Get notifications for a user, newest first."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            kwargs = {
                "KeyConditionExpression": Key("Pk").eq(f"USER#{user_id}")
                & Key("Sk").begins_with("NOTIFICATION#"),
                "ScanIndexForward": False,
                "Limit": limit,
            }
            if next_token:
                kwargs["ExclusiveStartKey"] = {
                    "Pk": f"USER#{user_id}",
                    "Sk": next_token,
                }

            try:
                response = await table.query(**kwargs)

                items = [
                    record_to_notification(item)
                    for item in response.get("Items", [])
                ]

                last_key = response.get("LastEvaluatedKey")
                token = last_key.get("Sk") if last_key else None

                return NotificationListResponse(items=items, next_token=token)

            except ClientError as e:
                logger.error(f"Error getting notifications for {user_id}: {e}")
                return NotificationListResponse(items=[])

    async def get_unread_count(self, user_id: str) -> UnreadCountResponse:
        """Count unread notifications for a user."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.query(
                    KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                    & Key("Sk").begins_with("NOTIFICATION#"),
                    FilterExpression="attribute_not_exists(read_at)",
                    Select="COUNT",
                )

                count = response.get("Count", 0)
                # Count only covers one page; paginate through remaining
                last_key = response.get("LastEvaluatedKey")
                while last_key:
                    response = await table.query(
                        KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                        & Key("Sk").begins_with("NOTIFICATION#"),
                        FilterExpression="attribute_not_exists(read_at)",
                        Select="COUNT",
                        ExclusiveStartKey=last_key,
                    )
                    count += response.get("Count", 0)
                    last_key = response.get("LastEvaluatedKey")

                return UnreadCountResponse(count=count)

            except ClientError as e:
                logger.error(f"Error getting unread count for {user_id}: {e}")
                return UnreadCountResponse(count=0)

    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a single notification as read. Updates canonical + user list item."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            now = datetime.utcnow().isoformat()

            try:
                # Get canonical to find created_at (needed for user list key)
                response = await table.get_item(
                    Key=NotificationEntityKeys.metadata_key(notification_id),
                    ProjectionExpression="created_at, recipient_id",
                )
                item = response.get("Item")
                if not item:
                    return False
                if item.get("recipient_id") != user_id:
                    return False

                created_at = item["created_at"]
                user_key = NotificationEntityKeys.user_notification_key(user_id, created_at, notification_id)

                # Update both items
                update_expr = "SET read_at = :now"
                expr_vals = {":now": now}

                await table.update_item(
                    Key=NotificationEntityKeys.metadata_key(notification_id),
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_vals,
                )
                await table.update_item(
                    Key=user_key,
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_vals,
                )

                return True

            except ClientError as e:
                logger.error(f"Error marking notification {notification_id} as read: {e}")
                return False

    async def mark_all_as_read(self, user_id: str) -> bool:
        """Mark all unread notifications as read for a user."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            now = datetime.utcnow().isoformat()

            try:
                # Query all unread user notification items
                response = await table.query(
                    KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                    & Key("Sk").begins_with("NOTIFICATION#"),
                    FilterExpression="attribute_not_exists(read_at)",
                )
                items = response.get("Items", [])
                last_key = response.get("LastEvaluatedKey")
                while last_key:
                    resp = await table.query(
                        KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                        & Key("Sk").begins_with("NOTIFICATION#"),
                        FilterExpression="attribute_not_exists(read_at)",
                        ExclusiveStartKey=last_key,
                    )
                    items.extend(resp.get("Items", []))
                    last_key = resp.get("LastEvaluatedKey")

                update_expr = "SET read_at = :now"
                expr_vals = {":now": now}

                for item in items:
                    # User list item
                    await table.update_item(
                        Key={"Pk": item["Pk"], "Sk": item["Sk"]},
                        UpdateExpression=update_expr,
                        ExpressionAttributeValues=expr_vals,
                    )
                    # Canonical item
                    await table.update_item(
                        Key=NotificationEntityKeys.metadata_key(item["notification_id"]),
                        UpdateExpression=update_expr,
                        ExpressionAttributeValues=expr_vals,
                    )

                return True

            except ClientError as e:
                logger.error(f"Error marking all notifications as read for {user_id}: {e}")
                return False


notification_service = NotificationService()
