from typing import List
from datetime import datetime
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.follow import Follow, FollowWithUser
from app.models.user import UserSearch
from app.services.user_service import user_service
import logging

logger = logging.getLogger(__name__)


class FollowService:
    def __init__(self):
        self.table_name = settings.follows_table
    
    async def follow_user(self, follower_id: str, following_id: str) -> bool:
        """Follow a user"""
        if follower_id == following_id:
            return False  # Can't follow yourself
        
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            follow_item = {
                'follower_id': follower_id,
                'following_id': following_id,
                'created_at': datetime.utcnow().isoformat()
            }
            
            try:
                await table.put_item(
                    Item=follow_item,
                    ConditionExpression='attribute_not_exists(follower_id) AND attribute_not_exists(following_id)'
                )
                
                # Update counters
                await user_service.increment_following_count(follower_id)
                await user_service.increment_followers_count(following_id)
                
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    # Already following
                    return False
                logger.error(f"Error following user: {e}")
                return False
    
    async def unfollow_user(self, follower_id: str, following_id: str) -> bool:
        """Unfollow a user"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                await table.delete_item(
                    Key={
                        'follower_id': follower_id,
                        'following_id': following_id
                    }
                )
                
                # Update counters
                await user_service.increment_following_count(follower_id, -1)
                await user_service.increment_followers_count(following_id, -1)
                
                return True
                
            except ClientError as e:
                logger.error(f"Error unfollowing user: {e}")
                return False
    
    async def is_following(self, follower_id: str, following_id: str) -> bool:
        """Check if user is following another user"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.get_item(
                    Key={
                        'follower_id': follower_id,
                        'following_id': following_id
                    }
                )
                return 'Item' in response
                
            except ClientError as e:
                logger.error(f"Error checking follow status: {e}")
                return False
    
    async def get_followers(self, user_id: str, limit: int = 20) -> List[FollowWithUser]:
        """Get followers of a user"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.query(
                    IndexName='following_id-follower_id-index',
                    KeyConditionExpression=Key('following_id').eq(user_id),
                    Limit=limit
                )
                
                followers = []
                for item in response['Items']:
                    # Get follower user info
                    user = await user_service.get_user_by_id(item['follower_id'])
                    if user:
                        user_search = UserSearch(
                            user_id=user.user_id,
                            username=user.username,
                            avatar_url=user.avatar_url,
                            bio=user.bio,
                            followers_count=user.followers_count
                        )
                        
                        follow = Follow(**item)
                        followers.append(FollowWithUser(**follow.dict(), user=user_search))
                
                return followers
                
            except ClientError as e:
                logger.error(f"Error getting followers for {user_id}: {e}")
                return []
    
    async def get_following(self, user_id: str, limit: int = 20) -> List[FollowWithUser]:
        """Get users that a user is following"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.query(
                    KeyConditionExpression=Key('follower_id').eq(user_id),
                    Limit=limit
                )
                
                following = []
                for item in response['Items']:
                    # Get following user info
                    user = await user_service.get_user_by_id(item['following_id'])
                    if user:
                        user_search = UserSearch(
                            user_id=user.user_id,
                            username=user.username,
                            avatar_url=user.avatar_url,
                            bio=user.bio,
                            followers_count=user.followers_count
                        )
                        
                        follow = Follow(**item)
                        following.append(FollowWithUser(**follow.dict(), user=user_search))
                
                return following
                
            except ClientError as e:
                logger.error(f"Error getting following for {user_id}: {e}")
                return []
    
    async def get_following_ids(self, user_id: str) -> List[str]:
        """Get list of user IDs that a user is following (for feed generation)"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.query(
                    KeyConditionExpression=Key('follower_id').eq(user_id),
                    ProjectionExpression='following_id'
                )
                
                return [item['following_id'] for item in response['Items']]
                
            except ClientError as e:
                logger.error(f"Error getting following IDs for {user_id}: {e}")
                return []


# Global service instance
follow_service = FollowService()