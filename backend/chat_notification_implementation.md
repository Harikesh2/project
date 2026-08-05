# Chat unread-count badge (WebSocket) — implementation plan

**Goal:** Show a live unread-count badge on the Chat nav icon when someone messages you — same pattern as the existing notification bell (persist → `connection_manager.send_to_users` → frontend socket hook → TanStack cache → badge).

**Confirmed decisions:**
- Global nav icon badge ONLY (total count). No per-conversation badges.
- Count resets when you open that conversation.

**Pattern to copy (notifications):** `notification_service.get_unread_count()` → `GET /api/notifications/unread-count` → `{count}`; WS pushes `{type:"notification.created"}`; `useNotificationWs()` mounted once in `Layout` bumps the cache; badge reads the cache.

**Mechanism:** add `unread_count` to `UserInboxRecord` (one per user per conversation, rewritten on every message). Recipient's row = old + 1; sender's row = 0. Total = sum across the user's inbox rows.

---

## Phase 1 — Backend: unread_count on inbox + send_message increment

**Status: ✅ Completed**

| File | Change |
|------|--------|
| `backend/app/models/chat.py` | `unread_count: int = 0` on `UserInboxRecord` (field + `create()`); `to_dynamo_item` uses `exclude_none=True` so zero unread omits the attribute (backward compatible) |
| `backend/app/services/chat_service.py` | `send_message`: read recipient's old inbox row (`_get_inbox_unread`, default 0) before the transaction → new recipient row `unread_count = old + 1`, sender `= 0` |

Verify: `python -m pytest` / py_compile.

---

## Phase 2 — Backend: unread-count + mark-read endpoints

**Status: ✅ Completed** (verified in code)

| File | Change |
|------|--------|
| `backend/app/models/chat.py` | `ChatUnreadCountResponse` (`{count}`) |
| `backend/app/services/chat_service.py` | `get_unread_count(user_id)`: paginate `USER#{id}`/`CHAT#*`, sum `unread_count` (missing → 0). `mark_conversation_read(conversation_id, user_id)`: verify membership, set user's inbox row `unread_count = 0` |
| `backend/app/api/chat.py` | `GET /chats/unread-count` (declared **before** `/{conversation_id}`). ⚠️ Deviation: no `PUT /chats/{conversation_id}/read` route — mark-read happens as a side effect of `get_messages` (opening the conversation clears its badge) |

---

## Phase 3 — Frontend: chat WS hook + unread queries

**Status: ✅ Completed**

| File | Change |
|------|--------|
| `frontend/src/services/chatSocket.ts` | `connect()` made idempotent (early-return if already OPEN/CONNECTING) so global + page connects don't churn/reconnect |
| `frontend/src/services/chatService.ts` | `useChatUnreadCount` (cache `['chats','unread-count']`, 30s poll fallback). ⚠️ `useMarkConversationRead` **not added** — dead code, backend clears on `GET /messages` |

---

## Phase 4 — Frontend: nav badge + global WS subscription

**Status: ✅ Completed**

| File | Change |
|------|--------|
| `frontend/src/services/chatService.ts` | `useChatWs(currentUserId)` standalone hook (mirrors `useNotificationWs`): on `message.created` where `message.sender_id !== currentUserId`, bump `['chats','unread-count']`; also invalidate `['chats']` |
| `frontend/src/components/Layout.tsx` | Mounts `useChatWs(user?.user_id)` + `useChatUnreadCount()`; renders badge on Chat nav item (desktop + mobile), same markup as Notifications badge, gated on `item.name === 'Chat'` and not active on `/chats` |

---

## Phase 5 — Reset-on-open + tests

**Status: 🔶 Partial** (frontend done-by-design, backend test remaining)

| File | Change |
|------|--------|
| `frontend/src/context/ChatContext.tsx` / `Chat.tsx` | **Nothing to do** — opening a conversation calls `GET /messages`, which the backend auto-marks read; next badge refetch shows 0 |
| `backend/tests/` | ⬜ Still pending: test send → recipient +1, sender 0 → mark-read → 0 |

---

## Notes
- No new deps, no new DynamoDB items — reuses inbox rows + existing `/ws/chat` + TanStack cache.
- Inbox reads are read-then-transaction; fine for 2-party DM races.
- **Frontend complete.** Only remaining item is the backend test in Phase 5. Pre-existing build blocker (unrelated): unused `WifiOff` import in `frontend/src/components/chat/MessageComposer.tsx` fails `tsc`.
