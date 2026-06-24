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
            import os
            if not settings.aws_session_token:
                os.environ.pop('AWS_SESSION_TOKEN', None)
                
            kwargs = {
                'region_name': settings.aws_region,
                'aws_access_key_id': settings.aws_access_key_id,
                'aws_secret_access_key': settings.aws_secret_access_key
            }
            if settings.aws_session_token:
                kwargs['aws_session_token'] = settings.aws_session_token
            if settings.dynamodb_endpoint_url:
                kwargs['endpoint_url'] = settings.dynamodb_endpoint_url
            
            logger.info(f"Initializing DynamoDB client (Endpoint: {settings.dynamodb_endpoint_url or 'AWS Cloud'})")
            self._client = boto3.client('dynamodb', **kwargs)
        return self._client
    
    @property
    def resource(self) -> boto3.resource:
        """Get synchronous DynamoDB resource"""
        if self._resource is None:
            import os
            if not settings.aws_session_token:
                os.environ.pop('AWS_SESSION_TOKEN', None)
                
            kwargs = {
                'region_name': settings.aws_region,
                'aws_access_key_id': settings.aws_access_key_id,
                'aws_secret_access_key': settings.aws_secret_access_key
            }
            if settings.aws_session_token:
                kwargs['aws_session_token'] = settings.aws_session_token
            if settings.dynamodb_endpoint_url:
                kwargs['endpoint_url'] = settings.dynamodb_endpoint_url
            
            logger.info(f"Initializing DynamoDB resource (Endpoint: {settings.dynamodb_endpoint_url or 'AWS Cloud'})")
            self._resource = boto3.resource('dynamodb', **kwargs)
        return self._resource

    def get_async_resource(self):
        """Get asynchronous DynamoDB resource context manager"""
        import os
        if not settings.aws_session_token:
            os.environ.pop('AWS_SESSION_TOKEN', None)

        if self._async_session is None:
            session_kwargs = {
                'aws_access_key_id': settings.aws_access_key_id,
                'aws_secret_access_key': settings.aws_secret_access_key,
                'region_name': settings.aws_region,
            }
            # Only pass session token when it has a real value — passing None
            # can confuse boto3 into expecting temporary credential flow.
            if settings.aws_session_token:
                session_kwargs['aws_session_token'] = settings.aws_session_token

            self._async_session = aioboto3.Session(**session_kwargs)
            logger.info(
                f"aioboto3 Session created (region={settings.aws_region}, "
                f"key_id={settings.aws_access_key_id[:8]}..., "
                f"session_token={'yes' if settings.aws_session_token else 'no'})"
            )

        kwargs = {}
        if settings.dynamodb_endpoint_url:
            kwargs['endpoint_url'] = settings.dynamodb_endpoint_url

        return self._async_session.resource('dynamodb', **kwargs)


# Global connection instance
db_connection = DynamoDBConnection()