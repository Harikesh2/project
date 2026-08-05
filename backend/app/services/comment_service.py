from typing import List
from datetime import datetime
from uuid import uuid4
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.comment import (
    Comment,
    CommentCreate,
    CommentEntityKeys,
    PostCommentRecord,
    UserCommentRecord,
    record_to_comment,
    CommentWithUser,
)
from app.models.user import UserSearch
from app.services.user_service import user_service
from app.services.post_service import post_service
from app.services.notification_service import maybe_notify
import logging

logger = logging.getLogger(__name__)


class CommentService:
    def __init__(self):
        self.table_name = settings.comments_table

    async def create_comment(
        self, post_id: str, comment_data: CommentCreate, user_id: str
    ) -> Comment:
        """Create canonical POST comment + USER activity duplicate."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            comment_id = str(uuid4())
            now = datetime.utcnow().isoformat()

            canonical = PostCommentRecord.from_create(
                post_id, comment_data, user_id, comment_id, now
            )
            duplicate = UserCommentRecord.from_post_comment(canonical)

            try:
                await table.put_item(
                    Item=canonical.to_dynamo_item(),
                    ConditionExpression="attribute_not_exists(Sk)",
                )
                await table.put_item(Item=duplicate.to_dynamo_item())
                await post_service.increment_comments_count(post_id)

                # Notification: skip self-comments
                try:
                    post = await post_service.get_post_by_id(post_id)
                    if post:
                        await maybe_notify(
                            actor_id=user_id,
                            recipient_id=post.user_id,
                            type_="comment",
                            entity_id=post_id,
                            entity_type="post",
                            preview=comment_data.content[:100],
                        )
                except Exception:
                    logger.warning(
                        f"Failed to send comment notification for post {post_id}",
                        exc_info=True,
                    )

                return record_to_comment(canonical.to_dynamo_item())

            except ClientError as e:
                logger.error(f"Error creating comment: {e}")
                raise

    async def get_post_comments(self, post_id: str, limit: int = 20) -> List[CommentWithUser]:
        """Get comments for a post via POST#{id}, SK begins_with COMMENT#."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.query(
                    KeyConditionExpression=Key("Pk").eq(f"POST#{post_id}")
                    & Key("Sk").begins_with(CommentEntityKeys.COMMENT_PREFIX),
                    ScanIndexForward=True,
                    Limit=limit,
                )

                comments: List[CommentWithUser] = []
                for item in response["Items"]:
                    user = await user_service.get_user_by_id(item["user_id"])
                    if user:
                        comments.append(
                            CommentWithUser.from_comment_and_user(
                                record_to_comment(item), UserSearch.from_user(user)
                            )
                        )

                return comments

            except ClientError as e:
                logger.error(f"Error getting comments for post {post_id}: {e}")
                return []

    async def delete_comment(self, post_id: str, comment_id: str, user_id: str) -> bool:
        """Delete canonical and USER duplicate comment items."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.get_item(
                    Key=CommentEntityKeys.post_comment_key(post_id, comment_id)
                )

                if "Item" not in response:
                    return False

                if response["Item"]["user_id"] != user_id:
                    return False

                await table.delete_item(
                    Key=CommentEntityKeys.post_comment_key(post_id, comment_id)
                )
                await table.delete_item(
                    Key=CommentEntityKeys.user_comment_key(user_id, comment_id)
                )
                await post_service.increment_comments_count(post_id, -1)
                return True

            except ClientError as e:
                logger.error(f"Error deleting comment {comment_id}: {e}")
                return False


comment_service = CommentService()
