from typing import Optional, List
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.user import (
    User,
    UserCreate,
    UserUpdate,
    UserSearch,
    UserEntityKeys,
    UserMetadataRecord,
    UserProfileItem,
    merge_user_records,
)
import logging

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self):
        self.table_name = settings.users_table
        logger.info(f"UserService initialised with table_name='{self.table_name}'")

    async def _get_metadata(self, table, user_id: str) -> Optional[UserMetadataRecord]:
        response = await table.get_item(Key=UserEntityKeys.metadata_key(user_id))
        if "Item" not in response:
            return None
        return UserMetadataRecord.from_dynamo_item(response["Item"])

    async def _get_profile(self, table, user_id: str) -> Optional[UserProfileItem]:
        response = await table.get_item(Key=UserEntityKeys.profile_key(user_id))
        if "Item" not in response:
            return None
        return UserProfileItem.from_dynamo_item(response["Item"])

    async def _get_user_items(self, table, user_id: str) -> Optional[User]:
        metadata = await self._get_metadata(table, user_id)
        if not metadata:
            return None
        profile = await self._get_profile(table, user_id)
        return merge_user_records(metadata, profile)

    async def create_user(self, user_data: UserCreate, user_id: str) -> User:
        """Create a new user (METADATA + PROFILE items)."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            now = datetime.utcnow().isoformat()

            metadata = UserMetadataRecord.from_create(user_data, user_id, now)
            profile = UserProfileItem.from_create(user_data, user_id, now)

            try:
                await table.put_item(
                    Item=metadata.to_dynamo_item(),
                    ConditionExpression="attribute_not_exists(Sk)",
                )
                await table.put_item(Item=profile.to_dynamo_item())
                logger.info(f"Created user {user_id} in table '{self.table_name}'")
                return merge_user_records(metadata, profile)

            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    raise ValueError("User already exists")
                raise

    async def get_or_create_user(self, user_data: UserCreate, user_id: str) -> User:
        """Get an existing user or auto-create one if not found."""
        existing = await self.get_user_by_id(user_id)
        if existing:
            return existing
        logger.info(f"User {user_id} not found — auto-creating.")
        try:
            return await self.create_user(user_data, user_id)
        except ValueError:
            existing = await self.get_user_by_id(user_id)
            if existing:
                return existing
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID (METADATA + PROFILE)."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            try:
                return await self._get_user_items(table, user_id)
            except ClientError as e:
                logger.error(f"Error getting user {user_id}: {e}")
                raise

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email using GSI1-email-index."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            gsi1_pk, gsi1_sk = UserEntityKeys.gsi1_keys(email)

            try:
                response = await table.query(
                    IndexName=UserEntityKeys.GSI1_INDEX,
                    KeyConditionExpression=Key("GSI1PK").eq(gsi1_pk)
                    & Key("GSI1SK").eq(gsi1_sk),
                )
                if not response["Items"]:
                    return None
                metadata = UserMetadataRecord.from_dynamo_item(response["Items"][0])
                profile = await self._get_profile(table, metadata.user_id)
                return merge_user_records(metadata, profile)
            except ClientError as e:
                logger.error(f"Error getting user by email {email}: {e}")
                raise

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username using GSI2-username-index."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            gsi2_pk, gsi2_sk = UserEntityKeys.gsi2_keys(username)

            try:
                response = await table.query(
                    IndexName=UserEntityKeys.GSI2_INDEX,
                    KeyConditionExpression=Key("GSI2PK").eq(gsi2_pk)
                    & Key("GSI2SK").eq(gsi2_sk),
                )
                if not response["Items"]:
                    return None
                metadata = UserMetadataRecord.from_dynamo_item(response["Items"][0])
                profile = await self._get_profile(table, metadata.user_id)
                return merge_user_records(metadata, profile)
            except ClientError as e:
                logger.error(f"Error getting user by username {username}: {e}")
                raise

    async def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[User]:
        """Update user metadata and/or profile."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            now = datetime.utcnow().isoformat()

            metadata = await self._get_metadata(table, user_id)
            if not metadata:
                return None

            metadata_fields: list[str] = []
            expression_values: dict = {":updated_at": now}

            if user_data.username is not None:
                gsi2_pk, gsi2_sk = UserEntityKeys.gsi2_keys(user_data.username)
                metadata_fields.extend(
                    ["username = :username", "GSI2PK = :gsi2pk", "GSI2SK = :gsi2sk"]
                )
                expression_values[":username"] = user_data.username
                expression_values[":gsi2pk"] = gsi2_pk
                expression_values[":gsi2sk"] = gsi2_sk

            try:
                metadata_update = "SET updated_at = :updated_at"
                if metadata_fields:
                    metadata_update += ", " + ", ".join(metadata_fields)
                await table.update_item(
                    Key=UserEntityKeys.metadata_key(user_id),
                    UpdateExpression=metadata_update,
                    ExpressionAttributeValues=expression_values,
                )

                if user_data.avatar_url is not None or user_data.bio is not None:
                    profile_update = "SET updated_at = :updated_at"
                    profile_values: dict = {":updated_at": now}

                    if user_data.avatar_url is not None:
                        profile_update += ", avatar_url = :avatar_url"
                        profile_values[":avatar_url"] = user_data.avatar_url
                    if user_data.bio is not None:
                        profile_update += ", bio = :bio"
                        profile_values[":bio"] = user_data.bio

                    await table.update_item(
                        Key=UserEntityKeys.profile_key(user_id),
                        UpdateExpression=profile_update,
                        ExpressionAttributeValues=profile_values,
                    )

                return await self._get_user_items(table, user_id)

            except ClientError as e:
                logger.error(f"Error updating user {user_id}: {e}")
                raise

    async def delete_user(self, user_id: str) -> bool:
        """Delete user METADATA and PROFILE items."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                metadata = await self._get_metadata(table, user_id)
                if not metadata:
                    return False

                await table.delete_item(Key=UserEntityKeys.metadata_key(user_id))
                await table.delete_item(Key=UserEntityKeys.profile_key(user_id))
                logger.info(f"Deleted user {user_id}")
                return True
            except ClientError as e:
                logger.error(f"Error deleting user {user_id}: {e}")
                return False

    async def search_users(self, query: str, limit: int = 20) -> List[UserSearch]:
        """Search users by username (contains). Requires Scan — no GSI for partial match."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                response = await table.scan(
                    FilterExpression=(
                        Attr("Pk").begins_with(UserEntityKeys.USER_PK_PREFIX)
                        & Attr("Sk").eq(UserEntityKeys.METADATA_SK)
                        & Attr("username").contains(query)
                    ),
                    Limit=limit,
                )

                users: List[UserSearch] = []
                for item in response["Items"]:
                    user_id = item.get("user_id")
                    if not user_id:
                        continue
                    user = await self.get_user_by_id(user_id)
                    if user:
                        users.append(UserSearch.from_user(user))

                return users

            except ClientError as e:
                logger.error(f"Error searching users: {e}")
                raise

    async def increment_followers_count(self, user_id: str, increment: int = 1):
        """Increment followers count on METADATA."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                await table.update_item(
                    Key=UserEntityKeys.metadata_key(user_id),
                    UpdateExpression="ADD followers_count :inc",
                    ExpressionAttributeValues={":inc": increment},
                )
            except ClientError as e:
                logger.error(f"Error updating followers count for {user_id}: {e}")
                raise

    async def increment_following_count(self, user_id: str, increment: int = 1):
        """Increment following count on METADATA."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                await table.update_item(
                    Key=UserEntityKeys.metadata_key(user_id),
                    UpdateExpression="ADD following_count :inc",
                    ExpressionAttributeValues={":inc": increment},
                )
            except ClientError as e:
                logger.error(f"Error updating following count for {user_id}: {e}")
                raise

    async def increment_posts_count(self, user_id: str, increment: int = 1):
        """Increment posts count on METADATA."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                await table.update_item(
                    Key=UserEntityKeys.metadata_key(user_id),
                    UpdateExpression="ADD posts_count :inc",
                    ExpressionAttributeValues={":inc": increment},
                )
            except ClientError as e:
                logger.error(f"Error updating posts count for {user_id}: {e}")
                raise


user_service = UserService()
