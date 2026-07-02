"""
DynamoDB table setup script
Run this to create the single-table SocialMedia design with GSIs
"""
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
from app.database.connection import db_connection
import logging

logger = logging.getLogger(__name__)


def create_social_media_table():
    """Create the single SocialMedia table with PK/SK and GSIs."""
    table_name = settings.social_media_table

    try:
        table = db_connection.resource.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "Pk", "KeyType": "HASH"},
                {"AttributeName": "Sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "Pk", "AttributeType": "S"},
                {"AttributeName": "Sk", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
                {"AttributeName": "GSI3PK", "AttributeType": "S"},
                {"AttributeName": "GSI3SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1-email-index",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2-username-index",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI3-global-feed-index",
                    "KeySchema": [
                        {"AttributeName": "GSI3PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI3SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.wait_until_exists()
        logger.info(f"Created table: {table_name}")

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            logger.info(f"Table {table_name} already exists")
        else:
            logger.error(f"Error creating table {table_name}: {e}")
            raise


def create_all_tables():
    """Create the SocialMedia single table."""
    logger.info("Creating DynamoDB tables...")
    create_social_media_table()
    logger.info("All tables created successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_all_tables()
