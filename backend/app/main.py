from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os

# FORCE LOCAL DYNAMODB (Prevents UnrecognizedClientException from real AWS)
# os.environ["AWS_ENDPOINT_URL_DYNAMODB"] = "http://127.0.0.1:8001"
# os.environ["AWS_ENDPOINT_URL"] = "http://127.0.0.1:8001"

from app.core.config import settings
from app.api import users, posts, upload

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