from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os

from app.core.config import settings
from app.api import users, posts, upload
from app.utils.aws_healthcheck import verify_aws_credentials, AWSValidationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Social Media API",
    description="A production-ready social media platform API",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)


@app.on_event("startup")
async def startup_event():
    """Verify AWS credentials and log settings on startup"""
    try:
        logger.info("Verifying AWS credentials on startup...")
        verify_aws_credentials()
    except AWSValidationError as e:
        logger.critical(f"AWS Initialization Failure: {e}")
        # Fail fast on startup if real AWS credentials are required and invalid
        raise SystemExit(f"Startup aborted due to AWS validation failure: {e}")
    """Log settings on startup (with masked sensitive info)"""
    # Using model_dump() for pydantic v2 if needed, but dict() works for both usually
    try:
        safe_settings = settings.model_dump()
    except AttributeError:
        safe_settings = settings.dict()
        
    # Mask sensitive keys
    for key in ['clerk_secret_key', 'aws_secret_access_key']:
        if key in safe_settings and safe_settings[key]:
            safe_settings[key] = "********"
    logger.info(f"Application started with settings: {safe_settings}")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler for better debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

from botocore.exceptions import ClientError

@app.exception_handler(ClientError)
async def botocore_client_error_handler(request: Request, exc: ClientError):
    error_code = exc.response.get('Error', {}).get('Code', 'Unknown')
    error_message = exc.response.get('Error', {}).get('Message', '')
    logger.error(f"Boto3 ClientError: {error_code} - {error_message}", exc_info=True)
    
    if error_code in ('InvalidClientTokenId', 'UnrecognizedClientException', 'AuthFailure', 'SignatureDoesNotMatch'):
        return JSONResponse(
            status_code=500,
            content={"error": "AWS credentials are invalid"}
        )
    elif error_code == 'ResourceNotFoundException':
        return JSONResponse(
            status_code=500,
            content={"error": "DynamoDB table not found"}
        )
    elif error_code in ('AccessDeniedException', 'AccessDenied'):
        return JSONResponse(
            status_code=500,
            content={"error": "Insufficient IAM permissions"}
        )
    
    return JSONResponse(
        status_code=500,
        content={"error": f"AWS Service Error: {error_message} ({error_code})"}
    )

# Include routers
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(upload.router, prefix="/api", tags=["upload"])

@app.get("/")
async def root():
    return {"message": "Social Media API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/health/aws")
async def health_aws():
    try:
        info = verify_aws_credentials()
        return {
            "status": "ok",
            "aws": {
                "account": info.get("account"),
                "arn": info.get("arn"),
                "region": info.get("region")
            }
        }
    except Exception as e:
        logger.error(f"AWS Health Check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e)
            }
        )