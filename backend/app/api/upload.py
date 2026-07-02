from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from app.services.s3_service import s3_service
from app.auth.clerk import get_current_user
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed image types
ALLOWED_EXTENSIONS = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # Validate file type
    if file.content_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    try:
        # Read file content
        content = await file.read()
        
        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File is too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024)}MB"
            )

        # Upload to S3
        result = s3_service.upload_file(
            file_content=content,
            file_name=file.filename,
            content_type=file.content_type,
            user_id=current_user["user_id"]
        )
        
        return {
            "message": "Upload successful",
            "url": result["url"],
            "key": result["key"]
        }
        
    except Exception as e:
        logger.error(f"Upload endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        await file.close()
