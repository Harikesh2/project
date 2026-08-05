from typing import List
from datetime import datetime
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.follow import (
    Follow,
    FollowWithUser,
    FollowEntityKeys,
    FollowingRecord,
    FollowerRecord,
    record_to_follow,
)
from app.models.user import UserSearch
from app.services.user_service import user_service
from app.services.notification_service import maybe_notify
import logging

logger = logging.getLogger(__name__)


class FollowService:
    def __init__(self):
        self.table_name = settings.follows_table

    async def follow_user(self, follower_id: str, following_id: str) -> bool:
        """Create duplicated FOLLOWING + FOLLOWER relationship items."""
        if follower_id == following_id:
            return False

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            now = datetime.utcnow().isoformat()

            following = FollowingRecord.create(follower_id, following_id, now)
            follower = FollowerRecord.create(follower_id, following_id, now)

            try:
                await table.put_item(
                    Item=following.to_dynamo_item(),
                    ConditionExpression="attribute_not_exists(Sk)",
                )
                await table.put_item(Item=follower.to_dynamo_item())

                await user_service.increment_following_count(follower_id)
                await user_service.increment_followers_count(following_id)

                # Notification: follower_id != following_id by guard above
                await maybe_notify(
                    actor_id=follower_id,
                    recipient_id=following_id,
                    type_="follow",
                    entity_id=follower_id,
                    entity_type="user",
                )

                return True

            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return False
                logger.error(f"Error following user: {e}")
                return False

    async def unfollow_user(self, follower_id: str, following_id: str) -> bool:
        """Delete both FOLLOWING and FOLLOWER relationship items."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                await table.delete_item(
                    Key=FollowEntityKeys.following_key(follower_id, following_id)
                )
                await table.delete_item(
                    Key=FollowEntityKeys.follower_key(following_id, follower_id)
                )

                await user_service.increment_following_count(follower_id, -1)
                await user_service.increment_followers_count(following_id, -1)

                return True

            except ClientError as e:
                logger.error(f"Error unfollowing user: {e}")
                return False

    async def is_following(self, follower_id: str, following_id: str) -> bool:
        """Check FOLLOWING edge exists."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.get_item(
                    Key=FollowEntityKeys.following_key(follower_id, following_id)
                )
                return "Item" in response

            except ClientError as e:
                logger.error(f"Error checking follow status: {e}")
                return False

    async def get_followers(self, user_id: str, limit: int = 20) -> List[FollowWithUser]:
        """Get followers via PK=USER#{id}, SK begins_with FOLLOWER#."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.query(
                    KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                    & Key("Sk").begins_with(FollowEntityKeys.FOLLOWER_PREFIX),
                    Limit=limit,
                )

                followers: List[FollowWithUser] = []
                for item in response["Items"]:
                    follow = record_to_follow(item)
                    user = await user_service.get_user_by_id(follow.follower_id)
                    if user:
                        followers.append(
                            FollowWithUser.from_follow_and_user(
                                follow, UserSearch.from_user(user)
                            )
                        )

                return followers

            except ClientError as e:
                logger.error(f"Error getting followers for {user_id}: {e}")
                return []

    async def get_following(self, user_id: str, limit: int = 20) -> List[FollowWithUser]:
        """Get following list via PK=USER#{id}, SK begins_with FOLLOWING#."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.query(
                    KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                    & Key("Sk").begins_with(FollowEntityKeys.FOLLOWING_PREFIX),
                    Limit=limit,
                )

                following: List[FollowWithUser] = []
                for item in response["Items"]:
                    follow = record_to_follow(item)
                    user = await user_service.get_user_by_id(follow.following_id)
                    if user:
                        following.append(
                            FollowWithUser.from_follow_and_user(
                                follow, UserSearch.from_user(user)
                            )
                        )

                return following

            except ClientError as e:
                logger.error(f"Error getting following for {user_id}: {e}")
                return []

    async def get_following_ids(self, user_id: str) -> List[str]:
        """Get user IDs being followed (for feed generation)."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.query(
                    KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                    & Key("Sk").begins_with(FollowEntityKeys.FOLLOWING_PREFIX),
                    ProjectionExpression="following_id",
                )

                return [item["following_id"] for item in response["Items"]]

            except ClientError as e:
                logger.error(f"Error getting following IDs for {user_id}: {e}")
                return []


follow_service = FollowService()
