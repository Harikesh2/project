"""
DynamoDB table setup script
Run this to create all required tables with proper indexes
"""
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
from app.database.connection import db_connection
import logging

logger = logging.getLogger(__name__)


def create_users_table():
    """Create users table with GSI for username lookup"""
    table_name = settings.users_table
    
    try:
        table = db_connection.resource.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'username',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'username-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'username',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        table.wait_until_exists()
        logger.info(f"Created table: {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            logger.info(f"Table {table_name} already exists")
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            raise

def create_posts_table():
    """Create posts table with GSI for user posts"""
    table_name = settings.posts_table
    
    try:
        table = db_connection.resource.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'post_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'post_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'created_at',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'user_id-created_at-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'user_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'created_at',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        table.wait_until_exists()
        logger.info(f"Created table: {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            logger.info(f"Table {table_name} already exists")
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            raise


def create_follows_table():
    """Create follows table with GSI for followers lookup"""
    table_name = settings.follows_table
    
    try:
        table = db_connection.resource.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'follower_id',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'following_id',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'follower_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'following_id',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'following_id-follower_id-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'following_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'follower_id',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        table.wait_until_exists()
        logger.info(f"Created table: {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            logger.info(f"Table {table_name} already exists")
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            raise
def create_likes_table():
    """Create likes table"""
    table_name = settings.likes_table
    
    try:
        table = db_connection.resource.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'post_id',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'post_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        table.wait_until_exists()
        logger.info(f"Created table: {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            logger.info(f"Table {table_name} already exists")
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            raise


def create_comments_table():
    """Create comments table"""
    table_name = settings.comments_table
    
    try:
        table = db_connection.resource.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'post_id',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'comment_id',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'post_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'comment_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        table.wait_until_exists()
        logger.info(f"Created table: {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            logger.info(f"Table {table_name} already exists")
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            raise


def create_all_tables():
    """Create all DynamoDB tables"""
    logger.info("Creating DynamoDB tables...")
    
    create_users_table()
    create_posts_table()
    create_follows_table()
    create_likes_table()
    create_comments_table()
    
    logger.info("All tables created successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_all_tables()