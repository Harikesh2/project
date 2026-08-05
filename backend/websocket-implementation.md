# WebSocket Chat — Micro-Phase Implementation Plan

Source: websocket-chat-plan.md
Goal: Complete the feature using very small, low-context tasks so each coding session stays tiny (<300 tokens if possible).

## Prerequisite — DynamoDB table must exist

The `SocialMedia` table must exist in DynamoDB before any chat (or other) endpoint works. Without it, every request returns **500** (global handler catches `ResourceNotFoundException`).

Create it once:

```bash
cd backend
python -m app.database.setup
```

---

## Phase 1 — Create chat key helpers

**File:** `app/models/chat.py`

### Task

* Add `build_conversation_id(user1, user2)`
* Add metadata key helper
* Add message key helper
* Add inbox key helper

### Done When

* Same two user IDs always produce the same conversation ID.

Reference: Conversation identity section.

> ✅ Completed

---

## Phase 2 — Add ConversationMetadataRecord

**File:** `app/models/chat.py`

### Task

* Create Pydantic model
* Fields:

  * `conversation_id`
  * `participant_ids`
  * `created_at`
  * `updated_at`
  * `last_message_preview`
  * `last_message_at`
* Add `to_dynamo_item()`

### Done When

* Metadata item serializes correctly for DynamoDB.

> ✅ Completed

---

## Phase 3 — Add ChatMessageRecord

**File:** `app/models/chat.py`

### Task

* Create Pydantic model
* Fields:

  * `message_id`
  * `sender_id`
  * `content`
  * `created_at`
  * `client_message_id`
* Add `to_dynamo_item()`

### Done When

* Message item contains `Sk=MESSAGE#...` format.

> ✅ Completed

---

## Phase 4 — Add UserInboxRecord

**File:** `app/models/chat.py`

### Task

* Create Pydantic model
* Fields:

  * `other_user_id`
  * `preview`
  * `updated_at`
  * `conversation_id`
* Add `to_dynamo_item()`

### Done When

* Inbox item serializes correctly for DynamoDB.

> ✅ Completed

---

## Phase 5 — Create ChatService skeleton

**File:** `app/services/chat_service.py`

### Task

Add empty methods only:

* `get_or_create_direct_conversation`
* `list_conversations`
* `get_messages`
* `send_message`
* `get_conversation_for_member`

### Done When

* Service imports successfully.

> ✅ Completed

---

## Phase 6 — Implement get_or_create_direct_conversation

**File:** `app/services/chat_service.py`

### Task

* Reject self-chat
* Verify recipient exists
* Try metadata `GetItem`
* If absent, transact-create metadata + 2 inbox rows
* Use conditional write on `METADATA`

### Done When

* Calling twice creates only one conversation.

> ✅ Completed

---

## Phase 7 — Implement list_conversations

**File:** `app/services/chat_service.py`

### Task

* Query `Pk=USER#{id}`
* `Sk begins_with CHAT#`
* `ScanIndexForward=False`
* Support `limit + cursor`

### Done When

* Returns newest conversations first.

> ✅ Completed

---

## Phase 8 — Implement membership check

**File:** `app/services/chat_service.py`

### Task

* Implement `get_conversation_for_member`
* Verify caller is one of the participants

### Done When

* Non-participant raises an authorization error.

> ✅ Completed

---

## Phase 9 — Implement get_messages

**File:** `app/services/chat_service.py`

### Task

* Verify membership
* Query conversation partition
* `Sk begins_with MESSAGE#`
* Support cursor pagination
* Return chronological order

### Done When

* History loads correctly page by page.

> ✅ Completed

---

## Phase 10 — Implement send_message transaction

**File:** `app/services/chat_service.py`

### Task

* Verify membership
* Create message item
* Update metadata preview/timestamp
* Delete old inbox rows
* Insert new inbox rows
* Wrap everything in `TransactWriteItems`

### Done When

* Message and inbox updates occur atomically.

> ✅ Completed

---

## Phase 11 — Add REST router

**File:** `app/api/chat.py`

### Routes

* `POST /api/chats/direct/{recipient_id}`
* `GET /api/chats`
* `GET /api/chats/{conversation_id}/messages`

### Done When

* Routes call ChatService methods successfully.

> ✅ Completed

---

## Phase 12 — Register router

**File:** `app/main.py`

### Task

* Include chat router under `/api/chats`

### Done When

* Endpoints appear in FastAPI docs.

> ✅ Completed

---

## Phase 13 — Add WebSocket auth helper

**File:** `app/auth/clerk.py`

### Task

* Implement `get_current_websocket_user(websocket)`
* Extract token from query string
* Verify with Clerk
* Return same user shape as HTTP auth

### Done When

* Valid token returns authenticated user.

> ✅ Completed

---

## Phase 14 — Create ConnectionManager

**File:** `app/services/connection_manager.py`

### Methods

* `connect`
* `disconnect`
* `send_to_users`

### Done When

* Multiple sockets can be tracked per user.

> ✅ Completed

---

## Phase 15 — Add WebSocket endpoint

**File:** `app/api/chat_websocket.py`

### Task

* Authenticate before `accept()`
* Register socket
* Receive JSON
* Validate `message.send` event
* Call `send_message()`
* Broadcast `message.created`
* Cleanup in `finally`

### Done When

* Real-time delivery works between two connected users.

> ✅ Completed

---

# Frontend Micro-Phases

## F1 — Add chat types

**File:** `frontend/src/types/index.ts`

Add conversation, message, page, and WebSocket event types.

> ✅ Completed

---

## F2 — Add REST service

**File:** `frontend/src/services/chatService.ts`

Add methods for:

* Open conversation
* List conversations
* Load messages

> ✅ Completed

---

## F3 — Add singleton WebSocket service

**File:** `frontend/src/services/chatSocket.ts`

### Features

* Get fresh Clerk token
* Connect using `wss://` or `ws://`
* Reconnect with backoff
* Expose send/listen helpers

> ✅ Completed

---

## F4 — Add inbox page

**File:** `frontend/src/pages/Chats.tsx`

Show conversation list with latest preview and timestamp.

> ✅ Completed

---

## F5 — Add conversation page

**File:** `frontend/src/pages/Chat.tsx`

Load and display paginated message history.

> ✅ Completed

---

## F6 — Add message composer

**File:** `frontend/src/components/chat/MessageComposer.tsx`

### Features

* Input validation
* Send on submit
* Optimistic pending message using `client_message_id`

> ✅ Completed

---

## F7 — Add routes

**File:** `frontend/src/App.tsx`

Register:

* `/chats`
* `/chats/:conversationId`

> ✅ Completed

---

## F8 — Add profile Message button

**File:** `frontend/src/pages/Profile.tsx`

### Behavior

* Open/create direct conversation
* Navigate to chat page
* Hide button for current user

> ✅ Completed

---

# Recommended Execution Order

1. **P1–P4** → Models only
2. **P5–P10** → Service + DynamoDB
3. **P11–P12** → REST API
4. **P13–P15** → WebSocket
5. **F1–F8** → Frontend

---

# Low-Context Prompt Template

Use this template for each coding session:

```
Implement Phase X only.

File: <target file>

Task:
- bullet 1
- bullet 2
- bullet 3

Do not modify any other file.
Do not implement future phases.
Keep changes under 80 lines if possible.
```

This keeps each interaction small and minimizes token usage while still following the original implementation plan.
