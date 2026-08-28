from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.post import (
    Post,
    PostCreate,
    PostUpdate,
    PostWithUser,
    PostEntityKeys,
    PostMetadataRecord,
    UserTimelinePostRecord,
    record_to_post,
    is_legacy_timeline_post,
)
from app.models.user import User, UserSearch
from app.services.user_service import user_service
from app.services.embedding_service import embedding_service
import logging

logger = logging.getLogger(__name__)


class PostService:
    def __init__(self):
        self.table_name = settings.posts_table

    async def _find_legacy_timeline_item(self, table, post_id: str) -> Optional[dict]:
        """Find a legacy USER#/POST#{id} item. Scan Limit applies before filters, so paginate."""
        timeline_sk = PostEntityKeys.timeline_sk(post_id)
        filter_expression = Attr("Sk").eq(timeline_sk) & Attr("Pk").begins_with("USER#")

        last_evaluated_key = None
        while True:
            scan_kwargs: dict = {"FilterExpression": filter_expression}
            if last_evaluated_key:
                scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

            response = await table.scan(**scan_kwargs)
            items = response.get("Items", [])
            if items:
                return items[0]

            last_evaluated_key = response.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break

        return None

    async def _get_raw_post_item(self, table, post_id: str) -> Optional[dict]:
        """Resolve post from canonical METADATA or legacy USER#/POST#{id} timeline item."""
        response = await table.get_item(Key=PostEntityKeys.metadata_key(post_id))
        if "Item" in response:
            return response["Item"]

        return await self._find_legacy_timeline_item(table, post_id)

    async def _ensure_canonical_post(self, table, item: dict) -> None:
        """Lazy-migrate legacy timeline-only posts to POST#/METADATA."""
        post_id = item["post_id"]
        existing = await table.get_item(Key=PostEntityKeys.metadata_key(post_id))
        if "Item" in existing:
            return

        metadata = PostMetadataRecord.from_timeline_item(item)
        await table.put_item(
            Item=metadata.to_dynamo_item(),
            ConditionExpression="attribute_not_exists(Sk)",
        )
        logger.info(f"Lazy-migrated legacy post {post_id} to canonical METADATA")

    async def _get_existing_post_keys(
        self, table, post_id: str, user_id: str
    ) -> List[dict[str, str]]:
        """Return DynamoDB keys for all post representations that exist."""
        keys: List[dict[str, str]] = []

        metadata = await table.get_item(Key=PostEntityKeys.metadata_key(post_id))
        if "Item" in metadata:
            keys.append(PostEntityKeys.metadata_key(post_id))

        timeline = await table.get_item(Key=PostEntityKeys.timeline_key(user_id, post_id))
        if "Item" in timeline:
            keys.append(PostEntityKeys.timeline_key(user_id, post_id))

        return keys

    async def _update_all_post_items(
        self,
        table,
        post_id: str,
        user_id: str,
        update_expression: str,
        expression_values: dict,
    ):
        """Update every existing representation (canonical and/or legacy timeline)."""
        keys = await self._get_existing_post_keys(table, post_id, user_id)
        if not keys:
            logger.warning(f"No post keys found to update for post_id={post_id}")
            return

        for key in keys:
            await table.update_item(
                Key=key,
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
            )

    async def create_post(self, post_data: PostCreate, user_id: str) -> Post:
        """Create canonical METADATA + USER timeline duplicate."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            post_id = str(uuid4())
            now = datetime.utcnow().isoformat()

            metadata = PostMetadataRecord.from_create(post_data, post_id, user_id, now)
            timeline = UserTimelinePostRecord.from_metadata(metadata)

            try:
                await table.put_item(
                    Item=metadata.to_dynamo_item(),
                    ConditionExpression="attribute_not_exists(Pk) AND attribute_not_exists(Sk)",
                )
                await table.put_item(Item=timeline.to_dynamo_item())
                await user_service.increment_posts_count(user_id)

                # Embed post vector (best-effort)
                try:
                    user = await user_service.get_user_by_id(user_id)
                    username = user.username if user else user_id
                    embedding_service.upsert_post(post_id, user_id, username, post_data.content)
                except Exception as e:
                    logger.error(f"Failed to embed post {post_id}: {e}")

                return record_to_post(metadata.to_dynamo_item())

            except ClientError as e:
                logger.error(f"Error creating post: {e}")
                raise

    async def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """Get post by ID; supports legacy timeline-only items with lazy migration."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                item = await self._get_raw_post_item(table, post_id)
                if not item:
                    return None

                if is_legacy_timeline_post(item):
                    await self._ensure_canonical_post(table, item)

                return record_to_post(item)

            except ClientError as e:
                logger.error(f"Error getting post {post_id}: {e}")
                raise

    async def get_global_feed(self, limit: int = 20, last_key: Optional[dict] = None) -> List[Post]:
        """Get newest posts globally via GSI3-global-feed-index."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                query_kwargs = {
                    "IndexName": PostEntityKeys.GSI3_INDEX,
                    "KeyConditionExpression": Key("GSI3PK").eq(PostEntityKeys.GSI3_PK),
                    "ScanIndexForward": False,
                    "Limit": limit,
                }
                if last_key:
                    query_kwargs["ExclusiveStartKey"] = last_key

                response = await table.query(**query_kwargs)
                return [record_to_post(item) for item in response["Items"]]

            except ClientError as e:
                logger.error(f"Error getting global feed: {e}")
                return []

    async def batch_get_posts(self, post_ids: List[str]) -> List[Post]:
        """Fetch multiple posts by ID via BatchGetItem, preserving input order."""
        if not post_ids:
            return []

        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            items: dict[str, dict] = {}
            for i in range(0, len(post_ids), 100):
                chunk = post_ids[i : i + 100]
                try:
                    response = await dynamodb.batch_get_item(
                        RequestItems={
                            self.table_name: {
                                "Keys": [
                                    PostEntityKeys.metadata_key(pid) for pid in chunk
                                ]
                            }
                        }
                    )
                    for item in response.get("Responses", {}).get(self.table_name, []):
                        post_id = item.get("post_id")
                        if post_id:
                            items[post_id] = item
                except ClientError as e:
                    logger.error(f"Error in batch_get_posts: {e}")

            return [record_to_post(items[pid]) for pid in post_ids if pid in items]

    async def get_user_posts(
        self, user_id: str, limit: int = 20, last_key: Optional[str] = None
    ) -> List[PostWithUser]:
        """Get posts by user via timeline item collection (SK begins_with POST#)."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                query_kwargs = {
                    "KeyConditionExpression": Key("Pk").eq(f"USER#{user_id}")
                    & Key("Sk").begins_with("POST#"),
                    "ScanIndexForward": False,
                    "Limit": limit,
                }

                if last_key:
                    query_kwargs["ExclusiveStartKey"] = {
                        "Pk": f"USER#{user_id}",
                        "Sk": last_key,
                    }

                response = await table.query(**query_kwargs)

                user = await user_service.get_user_by_id(user_id)
                if not user:
                    return []

                user_search = UserSearch.from_user(user)
                posts = [
                    PostWithUser.from_post_and_user(record_to_post(item), user_search)
                    for item in response["Items"]
                ]
                posts.sort(key=lambda x: x.created_at, reverse=True)
                return posts

            except ClientError as e:
                logger.error(f"Error getting user posts for {user_id}: {e}")
                return []

    async def get_user_posts_for_feed(
        self, table, user_id: str, limit: int = 10
    ) -> List[dict]:
        """Query posts for a user's timeline. Returns raw items (no user lookup)."""
        try:
            response = await table.query(
                KeyConditionExpression=Key("Pk").eq(f"USER#{user_id}")
                & Key("Sk").begins_with("POST#"),
                ScanIndexForward=False,
                Limit=limit,
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error getting feed posts for {user_id}: {e}")
            return []

    async def get_global_feed(self, table=None, limit: int = 20) -> List[dict]:
        """Get newest posts globally via GSI3. Opens own connection if table not provided."""
        try:
            if table is None:
                async with db_connection.get_async_resource() as dynamodb:
                    table = await dynamodb.Table(self.table_name)
                    response = await table.query(
                        IndexName=PostEntityKeys.GSI3_INDEX,
                        KeyConditionExpression=Key("GSI3PK").eq(PostEntityKeys.GSI3_PK),
                        ScanIndexForward=False,
                        Limit=limit,
                    )
                    return response.get("Items", [])
            response = await table.query(
                IndexName=PostEntityKeys.GSI3_INDEX,
                KeyConditionExpression=Key("GSI3PK").eq(PostEntityKeys.GSI3_PK),
                ScanIndexForward=False,
                Limit=limit,
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error getting global feed: {e}")
            return []

    async def update_post(
        self, post_id: str, user_id: str, post_data: PostUpdate
    ) -> Optional[Post]:
        """Update all existing post representations (canonical and/or legacy)."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            raw_item = await self._get_raw_post_item(table, post_id)
            if not raw_item or raw_item.get("user_id") != user_id:
                return None

            if is_legacy_timeline_post(raw_item):
                await self._ensure_canonical_post(table, raw_item)

            update_expression = "SET updated_at = :updated_at, GSI3SK = :updated_at"
            expression_values = {":updated_at": datetime.utcnow().isoformat()}

            if post_data.content is not None:
                update_expression += ", content = :content"
                expression_values[":content"] = post_data.content

            if post_data.image_url is not None:
                update_expression += ", image_url = :image_url"
                expression_values[":image_url"] = post_data.image_url

            try:
                await self._update_all_post_items(
                    table, post_id, user_id, update_expression, expression_values
                )

                # Re-embed if content changed (best-effort)
                if post_data.content is not None:
                    try:
                        user = await user_service.get_user_by_id(user_id)
                        username = user.username if user else user_id
                        embedding_service.upsert_post(
                            post_id, user_id, username, post_data.content
                        )
                    except Exception as e:
                        logger.error(f"Failed to re-embed post {post_id}: {e}")

                return await self.get_post_by_id(post_id)

            except ClientError as e:
                logger.error(f"Error updating post {post_id}: {e}")
                raise

    async def delete_post(self, post_id: str, user_id: str) -> bool:
        """Delete all existing post representations."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            raw_item = await self._get_raw_post_item(table, post_id)
            if not raw_item or raw_item.get("user_id") != user_id:
                return False

            try:
                keys = await self._get_existing_post_keys(table, post_id, user_id)
                if not keys:
                    keys = [PostEntityKeys.timeline_key(user_id, post_id)]

                for key in keys:
                    try:
                        await table.delete_item(Key=key)
                    except ClientError:
                        pass

                await user_service.increment_posts_count(user_id, -1)
                return True

            except ClientError as e:
                logger.error(f"Error deleting post {post_id}: {e}")
                return False

    async def search_posts(self, query: str, limit: int = 20) -> List[PostWithUser]:
        """Search posts by content on canonical METADATA and legacy timeline items."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                filter_expression = Attr("content").contains(query) & (
                    (
                        Attr("Pk").begins_with(PostEntityKeys.POST_PK_PREFIX)
                        & Attr("Sk").eq(PostEntityKeys.METADATA_SK)
                    )
                    | (
                        Attr("Pk").begins_with("USER#")
                        & Attr("Sk").begins_with("POST#")
                    )
                )

                seen_ids: set[str] = set()
                posts: List[PostWithUser] = []
                last_evaluated_key = None

                while len(posts) < limit:
                    scan_kwargs: dict = {"FilterExpression": filter_expression}
                    if last_evaluated_key:
                        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

                    response = await table.scan(**scan_kwargs)

                    for item in response.get("Items", []):
                        post_id = item.get("post_id")
                        if not post_id or post_id in seen_ids:
                            continue
                        seen_ids.add(post_id)

                        user = await user_service.get_user_by_id(item["user_id"])
                        if user:
                            posts.append(
                                PostWithUser.from_post_and_user(
                                    record_to_post(item), UserSearch.from_user(user)
                                )
                            )
                        if len(posts) >= limit:
                            break

                    last_evaluated_key = response.get("LastEvaluatedKey")
                    if not last_evaluated_key:
                        break

                return posts

            except ClientError as e:
                logger.error(f"Error searching posts: {e}")
                return []

    async def increment_likes_count(self, post_id: str, increment: int = 1):
        """Increment likes count on all existing post representations."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            raw_item = await self._get_raw_post_item(table, post_id)
            if not raw_item:
                return

            user_id = raw_item["user_id"]
            if is_legacy_timeline_post(raw_item):
                await self._ensure_canonical_post(table, raw_item)

            try:
                await self._update_all_post_items(
                    table,
                    post_id,
                    user_id,
                    "ADD likes_count :inc",
                    {":inc": increment},
                )
            except ClientError as e:
                logger.error(f"Error updating likes count for {post_id}: {e}")
                raise

    async def increment_comments_count(self, post_id: str, increment: int = 1):
        """Increment comments count on all existing post representations."""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)

            raw_item = await self._get_raw_post_item(table, post_id)
            if not raw_item:
                return

            user_id = raw_item["user_id"]
            if is_legacy_timeline_post(raw_item):
                await self._ensure_canonical_post(table, raw_item)

            try:
                await self._update_all_post_items(
                    table,
                    post_id,
                    user_id,
                    "ADD comments_count :inc",
                    {":inc": increment},
                )
            except ClientError as e:
                logger.error(f"Error updating comments count for {post_id}: {e}")
                raise


post_service = PostService()
