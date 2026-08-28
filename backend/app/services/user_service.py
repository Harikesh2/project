from typing import Optional, List
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.services.embedding_service import embedding_service
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

                # Embed user vector (best-effort)
                try:
                    embedding_service.upsert_user(
                        user_id, user_data.username, user_data.bio or ""
                    )
                except Exception as e:
                    logger.error(f"Failed to embed user {user_id}: {e}")

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

                # Re-embed if username or bio changed (best-effort)
                if user_data.username is not None or user_data.bio is not None:
                    try:
                        user = await self._get_user_items(table, user_id)
                        if user:
                            embedding_service.upsert_user(
                                user_id, user.username, user.bio or ""
                            )
                    except Exception as e:
                        logger.error(f"Failed to re-embed user {user_id}: {e}")

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

                # Delete user vector (best-effort)
                try:
                    embedding_service.delete_user_vector(user_id)
                except Exception as e:
                    logger.error(f"Failed to delete user vector {user_id}: {e}")

                return True
            except ClientError as e:
                logger.error(f"Error deleting user {user_id}: {e}")
                return False

    async def batch_get_users(self, user_ids: List[str]) -> List[User]:
        """Fetch multiple users by ID via BatchGetItem, preserving input order."""
        if not user_ids:
            return []

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            users: List[User] = []

            for i in range(0, len(user_ids), 100):
                chunk = user_ids[i : i + 100]
                try:
                    response = await table.batch_get_item(
                        RequestItems={
                            self.table_name: {
                                "Keys": [
                                    UserEntityKeys.metadata_key(uid) for uid in chunk
                                ]
                            }
                        }
                    )
                    id_to_user: dict[str, User] = {}
                    for item in response.get("Responses", {}).get(self.table_name, []):
                        uid = item.get("user_id")
                        if uid:
                            profile = await self._get_profile(table, uid)
                            user = merge_user_records(
                                UserMetadataRecord.from_dynamo_item(item), profile
                            )
                            id_to_user[uid] = user
                    users.extend(id_to_user[uid] for uid in user_ids if uid in id_to_user)
                except ClientError as e:
                    logger.error(f"Error in batch_get_users: {e}")

            return users

    async def search_users(self, query: str, limit: int = 20) -> List[UserSearch]:
        """Search users. Empty query returns recent; otherwise semantic search with keyword fallback."""
        if not query.strip():
            return await _recent_users(self, limit)

        # Semantic search via Pinecone
        user_ids = embedding_service.search_users(query, limit=limit)
        if user_ids:
            users = await self.batch_get_users(user_ids)
            if users:
                return [UserSearch.from_user(u) for u in users]

        # Fallback: keyword Scan
        return await _keyword_search_users(self, query, limit)

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


async def _recent_users(svc: "UserService", limit: int) -> List[UserSearch]:
    """Bounded scan for recent users (no GSI for latest users; fine at hobby scale)."""
    async with db_connection.get_async_resource() as dynamodb:
        table = await dynamodb.Table(svc.table_name)
        try:
            response = await table.scan(
                FilterExpression=(
                    Attr("Pk").begins_with(UserEntityKeys.USER_PK_PREFIX)
                    & Attr("Sk").eq(UserEntityKeys.METADATA_SK)
                ),
                Limit=limit,
            )
            users: List[UserSearch] = []
            for item in response["Items"]:
                uid = item.get("user_id")
                if not uid:
                    continue
                user = await svc.get_user_by_id(uid)
                if user:
                    users.append(UserSearch.from_user(user))
            return users
        except ClientError as e:
            logger.error(f"Error fetching recent users: {e}")
            return []


async def _keyword_search_users(
    svc: "UserService", query: str, limit: int
) -> List[UserSearch]:
    """Fallback keyword Scan on username (contains)."""
    async with db_connection.get_async_resource() as dynamodb:
        table = await dynamodb.Table(svc.table_name)
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
                uid = item.get("user_id")
                if not uid:
                    continue
                user = await svc.get_user_by_id(uid)
                if user:
                    users.append(UserSearch.from_user(user))
            return users
        except ClientError as e:
            logger.error(f"Error in keyword user search: {e}")
            return []


user_service = UserService()
