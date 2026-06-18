from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Clerk Authentication
    clerk_secret_key: str
    
    # AWS Configuration
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket_name: str = ""
    
    # DynamoDB Configuration
    dynamodb_table_prefix: str = "social_media"
    dynamodb_endpoint_url: str = ""  # Empty for AWS, set for local DynamoDB
    
    # Clerk Authentication Details
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    
    # API Configuration
    cors_origins: List[str] = ["http://localhost:5173"]
    debug: bool = False
    
    # Table Names (computed properties)
    @property
    def users_table(self) -> str:
        return f"{self.dynamodb_table_prefix}_users"
    
    @property
    def posts_table(self) -> str:
        return f"{self.dynamodb_table_prefix}_posts"
    
    @property
    def follows_table(self) -> str:
        return f"{self.dynamodb_table_prefix}_follows"
    
    @property
    def likes_table(self) -> str:
        return f"{self.dynamodb_table_prefix}_likes"
    
    @property
    def comments_table(self) -> str:
        return f"{self.dynamodb_table_prefix}_comments"

    class Config:
        # Use an absolute path if possible or ensure it looks in the right place
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        if not os.path.exists(env_file):
            env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()