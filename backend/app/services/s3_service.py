import boto3
import uuid
from botocore.exceptions import ClientError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.s3_aws_access_key_id or settings.aws_access_key_id,
            aws_secret_access_key=settings.s3_aws_secret_access_key or settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.bucket_name = settings.s3_bucket_name

    def upload_file(self, file_content: bytes, file_name: str, content_type: str, user_id: str = None) -> dict:
        """Upload file to S3 and return the URL"""
        try:
            # Generate unique key
            file_extension = file_name.split('.')[-1] if '.' in file_name else ''
            if user_id:
                unique_key = f"uploads/{user_id}/{uuid.uuid4()}.{file_extension}"
            else:
                unique_key = f"uploads/{uuid.uuid4()}.{file_extension}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=unique_key,
                Body=file_content,
                ContentType=content_type
                # Removed ACL - requires additional permissions
            )
            
            # Generate URL
            url = f"https://{self.bucket_name}.s3.{settings.aws_region}.amazonaws.com/{unique_key}"
            
            return {
                "url": url,
                "key": unique_key
            }
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise Exception(f"Failed to upload file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected upload error: {e}")
            raise Exception(f"Upload failed: {str(e)}")

    def delete_file(self, key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except ClientError as e:
            logger.error(f"S3 delete error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected delete error: {e}")
            return False

# Create singleton instance
s3_service = S3Service()