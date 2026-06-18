from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.post import Post, PostCreate, PostUpdate, PostWithUser
from app.models.user import UserSearch
from app.services.user_service import user_service
import logging

logger = logging.getLogger(__name__)


class PostService:
    def __init__(self):
        self.table_name = settings.posts_table
    
    async def create_post(self, post_data: PostCreate, user_id: str) -> Post:
        """Create a new post"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            post_id = str(uuid4())
            now = datetime.utcnow().isoformat()
            
            post_item = {
                'post_id': post_id,
                'user_id': user_id,
                'content': post_data.content,
                'image_url': post_data.image_url,
                'created_at': now,
                'updated_at': now,
                'likes_count': 0,
                'comments_count': 0
            }
            
            try:
                await table.put_item(Item=post_item)
                
                # Increment user's posts count
                await user_service.increment_posts_count(user_id)
                
                return Post(**post_item)
                
            except ClientError as e:
                logger.error(f"Error creating post: {e}")
                raise
    
    async def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """Get post by ID"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.get_item(Key={'post_id': post_id})
                if 'Item' in response:
                    return Post(**response['Item'])
                return None
                
            except ClientError as e:
                logger.error(f"Error getting post {post_id}: {e}")
                return None
    
    async def get_user_posts(self, user_id: str, limit: int = 20, last_key: Optional[str] = None) -> List[PostWithUser]:
        """Get posts by user with pagination"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                query_kwargs = {
                    'IndexName': 'user_id-created_at-index',
                    'KeyConditionExpression': Key('user_id').eq(user_id),
                    'ScanIndexForward': False,  # Sort by created_at descending
                    'Limit': limit
                }
                
                if last_key:
                    query_kwargs['ExclusiveStartKey'] = {'user_id': user_id, 'created_at': last_key}
                
                response = await table.query(**query_kwargs)
                
                posts = []
                user = await user_service.get_user_by_id(user_id)
                if user:
                    user_search = UserSearch(
                        user_id=user.user_id,
                        username=user.username,
                        avatar_url=user.avatar_url,
                        bio=user.bio,
                        followers_count=user.followers_count
                    )
                    
                    for item in response['Items']:
                        post = Post(**item)
                        posts.append(PostWithUser(**post.dict(), user=user_search))
                
                return posts
                
            except ClientError as e:
                logger.error(f"Error getting user posts for {user_id}: {e}")
                return []
    
    async def update_post(self, post_id: str, user_id: str, post_data: PostUpdate) -> Optional[Post]:
        """Update a post (only by owner)"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            # First check if post exists and belongs to user
            existing_post = await self.get_post_by_id(post_id)
            if not existing_post or existing_post.user_id != user_id:
                return None
            
            # Build update expression
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat()}
            
            if post_data.content is not None:
                update_expression += ", content = :content"
                expression_values[':content'] = post_data.content
            
            if post_data.image_url is not None:
                update_expression += ", image_url = :image_url"
                expression_values[':image_url'] = post_data.image_url
            
            try:
                response = await table.update_item(
                    Key={'post_id': post_id},
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expression_values,
                    ReturnValues='ALL_NEW'
                )
                
                if 'Attributes' in response:
                    return Post(**response['Attributes'])
                return None
                
            except ClientError as e:
                logger.error(f"Error updating post {post_id}: {e}")
                return None
    
    async def delete_post(self, post_id: str, user_id: str) -> bool:
        """Delete a post (only by owner)"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            # First check if post exists and belongs to user
            existing_post = await self.get_post_by_id(post_id)
            if not existing_post or existing_post.user_id != user_id:
                return False
            
            try:
                await table.delete_item(Key={'post_id': post_id})
                
                # Decrement user's posts count
                await user_service.increment_posts_count(user_id, -1)
                
                return True
                
            except ClientError as e:
                logger.error(f"Error deleting post {post_id}: {e}")
                return False
    
    async def search_posts(self, query: str, limit: int = 20) -> List[PostWithUser]:
        """Search posts by content"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                # Note: This is a scan operation which is not efficient for large datasets
                # In production, consider using ElasticSearch or similar for text search
                # DynamoDB contains is case-sensitive, so we use the query as is.
                response = await table.scan(
                    FilterExpression='contains(content, :query)',
                    ExpressionAttributeValues={':query': query},
                    Limit=limit
                )
                
                posts = []
                for item in response['Items']:
                    # Get user info for each post
                    user = await user_service.get_user_by_id(item['user_id'])
                    if user:
                        user_search = UserSearch(
                            user_id=user.user_id,
                            username=user.username,
                            avatar_url=user.avatar_url,
                            bio=user.bio,
                            followers_count=user.followers_count
                        )
                        
                        posts.append(PostWithUser(
                            post_id=item['post_id'],
                            user_id=item['user_id'],
                            content=item['content'],
                            image_url=item.get('image_url'),
                            created_at=item['created_at'],
                            updated_at=item.get('updated_at', item['created_at']),
                            likes_count=item.get('likes_count', 0),
                            comments_count=item.get('comments_count', 0),
                            user=user_search
                        ))
                
                return posts
                
            except ClientError as e:
                logger.error(f"Error searching posts: {e}")
                return []
    
    async def increment_likes_count(self, post_id: str, increment: int = 1):
        """Increment likes count"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                await table.update_item(
                    Key={'post_id': post_id},
                    UpdateExpression='ADD likes_count :inc',
                    ExpressionAttributeValues={':inc': increment}
                )
            except ClientError as e:
                logger.error(f"Error updating likes count for {post_id}: {e}")
    
    async def increment_comments_count(self, post_id: str, increment: int = 1):
        """Increment comments count"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                await table.update_item(
                    Key={'post_id': post_id},
                    UpdateExpression='ADD comments_count :inc',
                    ExpressionAttributeValues={':inc': increment}
                )
            except ClientError as e:
                logger.error(f"Error updating comments count for {post_id}: {e}")


# Global service instance
post_service = PostService()