from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
import logging

from app.core.config import settings
from app.database.connection import db_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["socialmedia"])

# Pydantic Schemas
class SocialMediaCreate(BaseModel):
    userId: str = Field(..., description="Partition key")
    postId: str = Field(..., description="Sort key")
    content: str = Field(..., description="Post content payload")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional custom metadata")

class SocialMediaResponse(BaseModel):
    userId: str
    postId: str
    content: str
    metadata: Dict[str, Any]

# Dependency for Asynchronous DynamoDB Resource
async def get_dynamodb_resource():
    """Dependency injection to provide thread-safe connection resource lifetime scope"""
    async with db_connection.get_async_resource() as resource:
        yield resource

@router.post("", response_model=SocialMediaResponse)
async def write_social_media(
    payload: SocialMediaCreate,
    dynamodb = Depends(get_dynamodb_resource)
):
    """
    Asynchronously write an incoming payload to the 'SocialMedia' DynamoDB table.
    """
    logger.info(f"Writing social media record: userId={payload.userId}, postId={payload.postId}")
    try:
        table = await dynamodb.Table(settings.social_media_table)
        
        # Pydantic V2/V1 compatible serialization
        try:
            item = payload.model_dump()
        except AttributeError:
            item = payload.dict()
            
        await table.put_item(Item=item)
        logger.info(f"Successfully saved record: userId={payload.userId}, postId={payload.postId}")
        return item
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', '')
        logger.error(f"ClientError saving record: Code={error_code}, Message={error_message}")
        
        if error_code == 'ResourceNotFoundException':
            raise HTTPException(status_code=404, detail="SocialMedia table not found.")
        elif error_code == 'ProvisionedThroughputExceededException':
            raise HTTPException(status_code=503, detail="DynamoDB throughput limit exceeded.")
        elif error_code in ('AccessDeniedException', 'AccessDenied'):
            raise HTTPException(status_code=403, detail="Insufficient IAM permissions to write to SocialMedia table.")
        
        raise HTTPException(status_code=500, detail=f"Database write error: {error_message}")
    except Exception as e:
        logger.error(f"Unexpected error saving record: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal database error: {str(e)}")

@router.get("/{userId}/{postId}", response_model=SocialMediaResponse)
async def read_social_media(
    userId: str,
    postId: str,
    dynamodb = Depends(get_dynamodb_resource)
):
    """
    Asynchronously read a record from the 'SocialMedia' DynamoDB table using partition and sort keys.
    """
    logger.info(f"Reading social media record: userId={userId}, postId={postId}")
    try:
        table = await dynamodb.Table(settings.social_media_table)
        response = await table.get_item(Key={"userId": userId, "postId": postId})
        
        if 'Item' not in response:
            logger.warning(f"Record not found: userId={userId}, postId={postId}")
            raise HTTPException(status_code=404, detail="Record not found.")
            
        logger.info(f"Successfully retrieved record: userId={userId}, postId={postId}")
        return response['Item']
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', '')
        logger.error(f"ClientError reading record: Code={error_code}, Message={error_message}")
        
        if error_code == 'ResourceNotFoundException':
            raise HTTPException(status_code=404, detail="SocialMedia table not found.")
        elif error_code in ('AccessDeniedException', 'AccessDenied'):
            raise HTTPException(status_code=403, detail="Insufficient IAM permissions to read from SocialMedia table.")
            
        raise HTTPException(status_code=500, detail=f"Database read error: {error_message}")
    except Exception as e:
        logger.error(f"Unexpected error reading record: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal database error: {str(e)}")
