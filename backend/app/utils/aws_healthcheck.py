import boto3
import os
import logging
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

class AWSValidationError(Exception):
    """Custom exception raised when AWS validation fails."""
    pass

def verify_aws_credentials() -> dict:
    """
    Verify AWS credentials by creating an STS client and calling get_caller_identity.
    Returns a dictionary with details on success or raises AWSValidationError on failure.
    """
    # Force dotenv settings validation first
    try:
        settings.validate_aws_config()
    except ValueError as e:
        raise AWSValidationError(f"Invalid environment configuration: {e}")

    # Remove AWS_SESSION_TOKEN if not explicitly configured in settings to prevent stale token usage
    if not settings.aws_session_token:
        os.environ.pop('AWS_SESSION_TOKEN', None)

    # If endpoint_url is configured for local DynamoDB mock testing, STS check can be skipped or mocked.
    if settings.dynamodb_endpoint_url:
        logger.info(f"DynamoDB endpoint URL is configured for local testing: {settings.dynamodb_endpoint_url}. Skipping STS healthcheck.")
        return {
            "account": "local-test-account",
            "arn": "arn:aws:iam::000000000000:root",
            "user_id": "local-test-user",
            "region": settings.aws_region,
            "mocked": True
        }

    # Initialize STS client explicitly using loaded settings
    kwargs = {
        'region_name': settings.aws_region,
        'aws_access_key_id': settings.aws_access_key_id,
        'aws_secret_access_key': settings.aws_secret_access_key
    }
    if settings.aws_session_token:
        kwargs['aws_session_token'] = settings.aws_session_token

    try:
        sts_client = boto3.client('sts', **kwargs)
        identity = sts_client.get_caller_identity()
        
        logger.info("AWS credentials validated successfully.")
        logger.info(f"Account: {identity.get('Account')}")
        logger.info(f"ARN: {identity.get('Arn')}")
        logger.info(f"Region: {settings.aws_region}")

        return {
            "account": identity.get("Account"),
            "arn": identity.get("Arn"),
            "user_id": identity.get("UserId"),
            "region": settings.aws_region,
            "mocked": False
        }
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"AWS Credential validation failed: Code={error_code}, Message={error_message}")
        
        if error_code in ('InvalidClientTokenId', 'UnrecognizedClientException'):
            raise AWSValidationError(
                "AWS credentials are invalid. The access key ID or secret access key is incorrect, or a stale security token was included."
            ) from e
        elif error_code == 'ExpiredToken':
            raise AWSValidationError("AWS credentials / temporary session token has expired.") from e
        elif error_code == 'AccessDenied':
            raise AWSValidationError("Insufficient IAM permissions for the configured principal.") from e
        else:
            raise AWSValidationError(f"AWS STS verification failed: {error_message} (Code: {error_code})") from e
    except Exception as e:
        logger.error(f"Unexpected error validating AWS credentials: {e}", exc_info=True)
        raise AWSValidationError(f"Unexpected error validating AWS credentials: {str(e)}") from e
