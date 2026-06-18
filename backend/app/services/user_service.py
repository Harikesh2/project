from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.user import User, UserCreate, UserUpdate, UserProfile, UserSearch
import logging

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self):
        self.table_name = settings.users_table
    
    async def create_user(self, user_data: UserCreate, user_id: str) -> User:
        """Create a new user"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            now = datetime.utcnow().isoformat()
            
            user_item = {
                'user_id': user_id,
                'username': user_data.username,
                'email': user_data.email,
                'avatar_url': user_data.avatar_url,
                'bio': user_data.bio,
                'created_at': now,
                'updated_at': now,
                'followers_count': 0,
                'following_count': 0,
                'posts_count': 0
            }
            
            try:
                await table.put_item(
                    Item=user_item,
                    ConditionExpression='attribute_not_exists(user_id)'
                )
                
                return User(**user_item)
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    raise ValueError("User already exists")
                raise
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.get_item(Key={'user_id': user_id})
                if 'Item' in response:
                    return User(**response['Item'])
                return None
                
            except ClientError as e:
                logger.error(f"Error getting user {user_id}: {e}")
                return None
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username using GSI"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                response = await table.query(
                    IndexName='username-index',
                    KeyConditionExpression=Key('username').eq(username)
                )
                
                if response['Items']:
                    return User(**response['Items'][0])
                return None
                
            except ClientError as e:
                logger.error(f"Error getting user by username {username}: {e}")
                return None
    
    async def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[User]:
        """Update user profile"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            # Build update expression
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat()}
            
            if user_data.username is not None:
                update_expression += ", username = :username"
                expression_values[':username'] = user_data.username
            
            if user_data.avatar_url is not None:
                update_expression += ", avatar_url = :avatar_url"
                expression_values[':avatar_url'] = user_data.avatar_url
            
            if user_data.bio is not None:
                update_expression += ", bio = :bio"
                expression_values[':bio'] = user_data.bio
            
            try:
                response = await table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expression_values,
                    ReturnValues='ALL_NEW'
                )
                
                if 'Attributes' in response:
                    return User(**response['Attributes'])
                return None
                
            except ClientError as e:
                logger.error(f"Error updating user {user_id}: {e}")
                return None

    async def search_users(self, query: str, limit: int = 20) -> List[UserSearch]:
        """Search users by username (simple contains search)"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                # Note: This is a scan operation which is not efficient for large datasets
                # DynamoDB contains is case-sensitive, so we use the query as is.
                response = await table.scan(
                    FilterExpression='contains(username, :query)',
                    ExpressionAttributeValues={':query': query},
                    Limit=limit
                )
                
                users = []
                for item in response['Items']:
                    users.append(UserSearch(
                        user_id=item['user_id'],
                        username=item['username'],
                        avatar_url=item.get('avatar_url'),
                        bio=item.get('bio'),
                        followers_count=item.get('followers_count', 0)
                    ))
                
                return users
                
            except ClientError as e:
                logger.error(f"Error searching users: {e}")
                return []
    
    async def increment_followers_count(self, user_id: str, increment: int = 1):
        """Increment followers count"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                await table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression='ADD followers_count :inc',
                    ExpressionAttributeValues={':inc': increment}
                )
            except ClientError as e:
                logger.error(f"Error updating followers count for {user_id}: {e}")
    
    async def increment_following_count(self, user_id: str, increment: int = 1):
        """Increment following count"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                await table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression='ADD following_count :inc',
                    ExpressionAttributeValues={':inc': increment}
                )
            except ClientError as e:
                logger.error(f"Error updating following count for {user_id}: {e}")
    
    async def increment_posts_count(self, user_id: str, increment: int = 1):
        """Increment posts count"""
        async with db_connection.get_async_resource() as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                await table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression='ADD posts_count :inc',
                    ExpressionAttributeValues={':inc': increment}
                )
            except ClientError as e:
                logger.error(f"Error updating posts count for {user_id}: {e}")


# Global service instance
user_service = UserService()