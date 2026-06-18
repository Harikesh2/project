import boto3
import aioboto3
from app.core.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DynamoDBConnection:
    def __init__(self):
        self._client: Optional[boto3.client] = None
        self._async_client = None
        self._resource: Optional[boto3.resource] = None
        self._async_session = None
    
    @property
    def client(self) -> boto3.client:
        """Get synchronous DynamoDB client"""
        if self._client is None:
            kwargs = {
                'region_name': settings.aws_region,
                'aws_access_key_id': settings.aws_access_key_id,
                'aws_secret_access_key': settings.aws_secret_access_key
            }
            if settings.dynamodb_endpoint_url:
                kwargs['endpoint_url'] = settings.dynamodb_endpoint_url
            
            logger.info(f"Initializing DynamoDB client (Endpoint: {settings.dynamodb_endpoint_url or 'AWS Cloud'})")
            self._client = boto3.client('dynamodb', **kwargs)
        return self._client
    
    @property
    def resource(self) -> boto3.resource:
        """Get synchronous DynamoDB resource"""
        if self._resource is None:
            kwargs = {
                'region_name': settings.aws_region,
                'aws_access_key_id': settings.aws_access_key_id,
                'aws_secret_access_key': settings.aws_secret_access_key
            }
            if settings.dynamodb_endpoint_url:
                kwargs['endpoint_url'] = settings.dynamodb_endpoint_url
            
            logger.info(f"Initializing DynamoDB resource (Endpoint: {settings.dynamodb_endpoint_url or 'AWS Cloud'})")
            self._resource = boto3.resource('dynamodb', **kwargs)
        return self._resource

    def get_async_resource(self):
        """Get asynchronous DynamoDB resource context manager"""
        if self._async_session is None:
            self._async_session = aioboto3.Session()
            
        kwargs = {
            'region_name': settings.aws_region,
            'aws_access_key_id': settings.aws_access_key_id,
            'aws_secret_access_key': settings.aws_secret_access_key
        }
        
        if settings.dynamodb_endpoint_url:
            kwargs['endpoint_url'] = settings.dynamodb_endpoint_url
            
        return self._async_session.resource('dynamodb', **kwargs)


# Global connection instance
db_connection = DynamoDBConnection()