from datetime import datetime
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.like import Like
from app.services.post_service import post_service
import logging

logger = logging.getLogger(__name__)


class LikeService:
    def __init__(self):
        self.table_name = settings.likes_table
    
    async def like_post(self, post_id: str, user_id: str) -> bool:
        """Like a post"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            like_item = {
                'Pk': f"POST#{post_id}",
                'Sk': f"LIKE#{user_id}",
                'post_id': post_id,
                'user_id': user_id,
                'created_at': datetime.utcnow().isoformat()
            }
            
            try:
                await table.put_item(
                    Item=like_item,
                    ConditionExpression='attribute_not_exists(Pk)'
                )
                
                # Increment post likes count
                await post_service.increment_likes_count(post_id)
                
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    # Already liked
                    return False
                logger.error(f"Error liking post: {e}")
                return False
    
    async def unlike_post(self, post_id: str, user_id: str) -> bool:
        """Unlike a post"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                await table.delete_item(
                    Key={
                        'Pk': f"POST#{post_id}",
                        'Sk': f"LIKE#{user_id}"
                    }
                )
                
                # Decrement post likes count
                await post_service.increment_likes_count(post_id, -1)
                
                return True
                
            except ClientError as e:
                logger.error(f"Error unliking post: {e}")
                return False
    
    async def is_liked(self, post_id: str, user_id: str) -> bool:
        """Check if user has liked a post"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.get_item(
                    Key={
                        'Pk': f"POST#{post_id}",
                        'Sk': f"LIKE#{user_id}"
                    }
                )
                return 'Item' in response
                
            except ClientError as e:
                logger.error(f"Error checking like status: {e}")
                return False


# Global service instance
like_service = LikeService()