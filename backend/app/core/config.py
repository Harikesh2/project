# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Clerk Authentication
    clerk_secret_key: str
    
    # AWS Configuration
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    aws_session_token: Optional[str] = None
    s3_bucket_name: str = "socialapp-621541294310-ap-south-1-an"
    
    # DynamoDB Configuration
    dynamodb_table_prefix: str = "SocialMedia"
    dynamodb_endpoint_url: str = ""  # Empty for AWS, set for local DynamoDB
    
    # Clerk Authentication Details
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    
    # API Configuration
    cors_origins: List[str] = ["http://localhost:5173"]
    debug: bool = False
    
    def validate_aws_config(self):
        """Validate AWS configurations and raise ValueError if invalid"""
        errors = []
        if not self.aws_access_key_id or not self.aws_access_key_id.strip():
            errors.append("AWS_ACCESS_KEY_ID is missing or empty")
        if not self.aws_secret_access_key or not self.aws_secret_access_key.strip():
            errors.append("AWS_SECRET_ACCESS_KEY is missing or empty")
        if not self.aws_region or not self.aws_region.strip():
            errors.append("AWS_REGION is missing or empty")
        
        if errors:
            raise ValueError(f"AWS Configuration Validation Failed: {', '.join(errors)}")

    
    # Table Names (computed properties)
    @property
    def users_table(self) -> str:
        return "SocialMedia"
    
    @property
    def posts_table(self) -> str:
        return "SocialMedia"
    
    @property
    def follows_table(self) -> str:
        return "SocialMedia"
    
    @property
    def likes_table(self) -> str:
        return "SocialMedia"
    
    @property
    def comments_table(self) -> str:
        return "SocialMedia"

    @property
    def social_media_table(self) -> str:
        return "SocialMedia"

    class Config:
        # Use an absolute path if possible or ensure it looks in the right place
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        if not os.path.exists(env_file):
            env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()