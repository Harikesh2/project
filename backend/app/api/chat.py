from typing import Dict, Any, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.clerk import get_current_user
from app.core.config import settings
from app.models.chat import (
    Conversation,
    ConversationPage,
    MessagePage,
    ChatUnreadCountResponse,
    SelfChatError,
    RecipientNotFoundError,
    ConversationNotFoundError,
    NotParticipantError,
    InvalidCursorError,
    ContentValidationError,
)
from app.services.chat_service import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chats"])


def _map_chat_error(exc: ChatError) -> HTTPException:
    """Map chat domain errors to the appropriate HTTP status codes."""
    if isinstance(exc, SelfChatError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, RecipientNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConversationNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, NotParticipantError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, (InvalidCursorError, ContentValidationError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/direct/{recipient_id}", response_model=Conversation)
async def open_direct_conversation(
    recipient_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Open or create a direct conversation with another user."""
    try:
        return await chat_service.get_or_create_direct_conversation(
            current_user["user_id"], recipient_id
        )
    except (SelfChatError, RecipientNotFoundError) as exc:
        raise _map_chat_error(exc)


@router.get("", response_model=ConversationPage)
async def list_conversations(
    limit: int = Query(settings.chat_default_conversation_limit, ge=1, le=settings.chat_max_conversation_limit),
    cursor: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List the current user's conversations, newest first."""
    try:
        return await chat_service.list_conversations(
            current_user["user_id"], limit, cursor
        )
    except (InvalidCursorError,) as exc:
        raise _map_chat_error(exc)


@router.get("/unread-count", response_model=ChatUnreadCountResponse)
async def get_unread_count(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Total unread messages across all conversations (badge count)."""
    return await chat_service.get_unread_count(current_user["user_id"])


@router.get("/{conversation_id}/messages", response_model=MessagePage)
async def get_messages(
    conversation_id: str,
    limit: int = Query(settings.chat_default_message_limit, ge=1, le=settings.chat_max_message_limit),
    cursor: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get paginated messages for a conversation (members only)."""
    try:
        return await chat_service.get_messages(
            conversation_id, current_user["user_id"], limit, cursor
        )
    except (ConversationNotFoundError, NotParticipantError, InvalidCursorError) as exc:
        raise _map_chat_error(exc)


@router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get conversation metadata (members only)."""
    try:
        metadata = await chat_service.get_conversation_for_member(
            conversation_id, current_user["user_id"]
        )
        return Conversation.from_metadata(metadata)
    except (ConversationNotFoundError, NotParticipantError) as exc:
        raise _map_chat_error(exc)
