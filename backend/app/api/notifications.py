from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional

from app.auth.clerk import get_current_user
from app.models.notification import (
    Notification,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.services.notification_service import notification_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


# ── Static routes MUST come before `/{id}` to avoid path-param capture ──

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get the count of unread notifications for the current user."""
    return await notification_service.get_unread_count(current_user["user_id"])


@router.put("/read-all", response_model=dict)
async def mark_all_read(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    success = await notification_service.mark_all_as_read(current_user["user_id"])
    return {"success": success}


# ── Dynamic routes ──

@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = Query(20, ge=1, le=50),
    next_token: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get paginated notifications for the current user, newest first."""
    return await notification_service.get_user_notifications(
        current_user["user_id"], limit=limit, next_token=next_token
    )


@router.put("/{notification_id}/read", response_model=dict)
async def mark_one_read(
    notification_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Mark a single notification as read."""
    success = await notification_service.mark_as_read(
        notification_id, current_user["user_id"]
    )
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}
