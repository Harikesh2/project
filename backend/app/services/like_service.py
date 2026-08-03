from typing import List
from datetime import datetime
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.like import (
    LikeEntityKeys,
    PostLikeRecord,
    UserLikeRecord,
)
from app.services.post_service import post_service
from app.services.user_service import user_service
from app.services.notification_service import notification_service
import logging

logger = logging.getLogger(__name__)


class LikeService:
    def __init__(self):
        self.table_name = settings.likes_table

    async def like_post(self, post_id: str, user_id: str) -> bool:
        """Create duplicated POST like + USER like items."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            now = datetime.utcnow().isoformat()

            post_like = PostLikeRecord.create(post_id, user_id, now)
            user_like = UserLikeRecord.create(post_id, user_id, now)

            try:
                await table.put_item(
                    Item=post_like.to_dynamo_item(),
                    ConditionExpression="attribute_not_exists(Sk)",
                )
                await table.put_item(Item=user_like.to_dynamo_item())
                await post_service.increment_likes_count(post_id)

                # Notification: skip self-likes
                try:
                    post = await post_service.get_post_by_id(post_id)
                    if post and post.user_id != user_id:
                        actor = await user_service.get_user_by_id(user_id)
                        if actor:
                            payload = {
                                "actor_username": actor.username,
                                "actor_avatar_url": actor.avatar_url,
                                "preview": post.content[:100],
                            }
                            await notification_service.create_notification(
                                recipient_id=post.user_id,
                                actor_id=user_id,
                                type_="like",
                                entity_id=post_id,
                                entity_type="post",
                                payload=payload,
                            )
                except Exception:
                    logger.warning(f"Failed to send like notification for post {post_id}", exc_info=True)

                return True

            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return False
                logger.error(f"Error liking post: {e}")
                return False

    async def unlike_post(self, post_id: str, user_id: str) -> bool:
        """Delete both POST like and USER like items."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                await table.delete_item(Key=LikeEntityKeys.post_like_key(post_id, user_id))
                await table.delete_item(Key=LikeEntityKeys.user_like_key(user_id, post_id))
                await post_service.increment_likes_count(post_id, -1)
                return True

            except ClientError as e:
                logger.error(f"Error unliking post: {e}")
                return False

    async def is_liked(self, post_id: str, user_id: str) -> bool:
        """Check if like exists on the post partition."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.get_item(
                    Key=LikeEntityKeys.post_like_key(post_id, user_id)
                )
                return "Item" in response

            except ClientError as e:
                logger.error(f"Error checking like status: {e}")
                return False

    async def get_liked_post_ids(self, user_id: str) -> List[str]:
        """Get post IDs liked by a user via USER#{id}, SK begins_with LIKE#."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.query(
                    KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                    & Key("Sk").begins_with(LikeEntityKeys.LIKE_PREFIX),
                    ProjectionExpression="post_id",
                )
                return [item["post_id"] for item in response["Items"]]

            except ClientError as e:
                logger.error(f"Error getting liked posts for {user_id}: {e}")
                return []


like_service = LikeService()
