from typing import List, Optional
from datetime import datetime
from uuid import uuid4
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.comment import Comment, CommentCreate, CommentUpdate, CommentWithUser
from app.models.user import UserSearch
from app.services.user_service import user_service
from app.services.post_service import post_service
import logging

logger = logging.getLogger(__name__)


class CommentService:
    def __init__(self):
        self.table_name = settings.comments_table
    
    async def create_comment(self, post_id: str, comment_data: CommentCreate, user_id: str) -> Comment:
        """Create a new comment"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            comment_id = str(uuid4())
            now = datetime.utcnow().isoformat()
            
            comment_item = {
                'post_id': post_id,
                'comment_id': comment_id,
                'user_id': user_id,
                'content': comment_data.content,
                'created_at': now,
                'updated_at': now
            }
            
            try:
                await table.put_item(Item=comment_item)
                
                # Increment post comments count
                await post_service.increment_comments_count(post_id)
                
                return Comment(**comment_item)
                
            except ClientError as e:
                logger.error(f"Error creating comment: {e}")
                raise
    
    async def get_post_comments(self, post_id: str, limit: int = 20) -> List[CommentWithUser]:
        """Get comments for a post"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.query(
                    KeyConditionExpression=Key('post_id').eq(post_id),
                    ScanIndexForward=True,  # Sort by comment_id ascending (chronological)
                    Limit=limit
                )
                
                comments = []
                for item in response['Items']:
                    # Get user info for each comment
                    user = await user_service.get_user_by_id(item['user_id'])
                    if user:
                        user_search = UserSearch(
                            user_id=user.user_id,
                            username=user.username,
                            avatar_url=user.avatar_url,
                            bio=user.bio,
                            followers_count=user.followers_count
                        )
                        
                        comment = Comment(**item)
                        comments.append(CommentWithUser(**comment.dict(), user=user_search))
                
                return comments
                
            except ClientError as e:
                logger.error(f"Error getting comments for post {post_id}: {e}")
                return []
    
    async def delete_comment(self, post_id: str, comment_id: str, user_id: str) -> bool:
        """Delete a comment (only by owner)"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            # First check if comment exists and belongs to user
            try:
                response = await table.get_item(
                    Key={
                        'post_id': post_id,
                        'comment_id': comment_id
                    }
                )
                
                if 'Item' not in response:
                    return False
                
                if response['Item']['user_id'] != user_id:
                    return False
                
                # Delete the comment
                await table.delete_item(
                    Key={
                        'post_id': post_id,
                        'comment_id': comment_id
                    }
                )
                
                # Decrement post comments count
                await post_service.increment_comments_count(post_id, -1)
                
                return True
                
            except ClientError as e:
                logger.error(f"Error deleting comment {comment_id}: {e}")
                return False


# Global service instance
comment_service = CommentService()