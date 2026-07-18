# WebSocket chat implementation plan

## Scope and decisions

This plan adds **one-to-one direct messages** between existing authenticated
users. It provides durable message history over REST and real-time delivery
over a WebSocket. Group chat, attachments, typing indicators, read receipts,
push notifications, moderation tooling, and multi-region/multi-worker message
fan-out are explicitly deferred.

The system will retain Clerk JWT authentication, FastAPI async services, and
the existing `SocialMedia` DynamoDB single table. No new database, cache,
queue, or DynamoDB GSI is required. This is important because the current
project rules rule out Redis and treat the single-table design as
load-bearing.

The initial deployment assumption is **one Uvicorn worker/process**. The
connection registry is process-local, so an in-memory WebSocket manager can
deliver to every tab connected to that process. Persisting first means an
offline recipient still receives the message through history; cross-process
live fan-out needs a separately approved managed pub/sub or WebSocket gateway
design before horizontal scaling.

## Existing architecture that constrains the feature

- `app/main.py` owns the FastAPI application, CORS, startup validation, and
  router registration. Existing protected HTTP routes authenticate with
  `Depends(get_current_user)` from `app/auth/clerk.py`.
- Routers in `app/api/` are thin. Stateful DynamoDB work belongs in singleton
  services under `app/services/`; Pydantic request/response and DynamoDB item
  records belong in `app/models/`.
- `SocialMedia` has only `Pk`/`Sk` plus the three existing user/feed GSIs.
  Relationship-like data is duplicated so each important read is a
  single-partition `Query`. Chat should follow that pattern and must not scan.
- DynamoDB access is asynchronous through
  `db_connection.get_async_resource()`. Existing services use UTC ISO strings
  and UUIDs, with `attribute_not_exists(Sk)` for composite-key conditional
  writes.
- The frontend is React/TypeScript. REST server state goes through TanStack
  Query service hooks, while `api.ts` is the single place that retrieves a
  Clerk token for axios. Native browser WebSockets cannot use axios or set an
  `Authorization` header.
- Tests currently use synchronous FastAPI `TestClient`, a local DynamoDB
  fixture, and an override for the HTTP auth dependency. WebSocket
  authentication needs its own test seam because it calls Clerk verification
  directly.

## Proposed data model and access patterns

All new item shapes use prefixes that do not overlap with existing
`USER#`, `POST#`, comment, like, or follow sort-key prefixes.

### Conversation identity

For a direct chat, derive a stable opaque ID from the two sorted user IDs:
`DM#{sha256("{smaller}:{larger}")}`. The ID is deterministic, so opening a
chat from either profile resolves to the same conversation without a scan or a
new index. The un-hashed IDs are stored only in the metadata participant list.

The service rejects a self-chat and verifies that the recipient exists. Every
subsequent read or send verifies that the caller is one of the two metadata
participants; knowing a conversation ID is never sufficient authorization.

| Item | Keys | Purpose / access pattern |
| --- | --- | --- |
| Conversation metadata | `Pk=CHAT#{conversation_id}`, `Sk=METADATA` | `GetItem` to authorize a caller and resolve the other participant. Stores `conversation_id`, sorted `participant_ids`, `created_at`, `updated_at`, `last_message_preview`, and `last_message_at`. |
| Message | `Pk=CHAT#{conversation_id}`, `Sk=MESSAGE#{created_at}#{message_id}` | `Query` with `Sk begins_with MESSAGE#`; ascending for an older-to-newer page, with an exclusive-start-key cursor. Stores `message_id`, `sender_id`, bounded `content`, `created_at`, and client idempotency key. |
| Per-user inbox projection | `Pk=USER#{user_id}`, `Sk=CHAT#{updated_at}#{conversation_id}` | `Query` with `Sk begins_with CHAT#`, `ScanIndexForward=False`, to list conversations newest first without a GSI. Stores the other participant ID, preview, and timestamp for rendering the inbox. |

On every persisted message, atomically add the message, update metadata, and
replace the two inbox projection rows. The old inbox sort keys are derived from
the metadata's previous `updated_at`; the new keys use the new timestamp. Use
one DynamoDB `TransactWriteItems` call for this write set (and a conditional
metadata update) so a conversation cannot show a preview without its message
or be updated for only one participant. Conversation creation likewise
transacts metadata plus both initial inbox projections and uses a conditional
write on `METADATA` to make concurrent opens idempotent. If a conditional
creation loses a race, read the winning metadata and return it.

The first version deliberately does not create user activity copies of every
message: messages are queried through their conversation partition and each
user has a compact inbox projection. This is the equivalent of the project's
existing duplicated-edge strategy, without making a user's partition grow by
every message.

## HTTP and WebSocket contract

REST supplies navigation and recovery; the WebSocket is for live delivery.
All timestamps are ISO-8601 UTC strings and all pagination cursors are
opaque encoded DynamoDB keys, not client-constructed sort keys.

| Operation | Contract | Notes |
| --- | --- | --- |
| Open/get direct conversation | `POST /api/chats/direct/{recipient_id}` → `Conversation` | Creates idempotently if absent; use this before navigation to the chat page. |
| List inbox | `GET /api/chats?limit=20&cursor=...` → `ConversationPage` | Uses the user's inbox projection query. |
| Load history | `GET /api/chats/{conversation_id}/messages?limit=50&cursor=...` → `MessagePage` | Requires membership. The first page returns newest messages in display order; older-page fetching preserves chronological rendering. |
| Connect | `GET /ws/chat?token=<Clerk JWT>` upgrade | The browser obtains the token with Clerk immediately before connecting. The backend verifies it before `accept()` and closes unauthorized upgrades with code `1008`. It must never log the URL/token. |
| Send event | `{ "type": "message.send", "conversation_id", "client_message_id", "content" }` | Validate with a Pydantic event model; reject blank/over-limit content, unknown event types, and non-membership. `client_message_id` makes reconnect retries idempotent. |
| Server message | `{ "type": "message.created", "conversation", "message", "client_message_id" }` | Broadcast to every connected tab of both members only after the DynamoDB transaction succeeds. The sender uses `client_message_id` to reconcile its optimistic item. |
| Errors/status | `{ "type": "error", "code", "detail" }` and `{ "type": "ready" }` | Per-event validation/authorization errors keep the socket open; unrecoverable authentication errors close it. |

Passing a short-lived JWT in the WebSocket query is necessary with the native
browser API under the current client architecture. Mitigations are: HTTPS/WSS
in production, no URL/query logging in the application or proxy, token
redaction in error handling, immediate verification, and reconnect with a
fresh token. If the deployment proxy cannot meet those constraints, replace
this with a short-lived one-time WebSocket ticket endpoint before release.

## Backend design

### Models

Add `app/models/chat.py` with:

- `ChatEntityKeys` for canonical metadata, message, and inbox keys;
- DynamoDB records (`ConversationMetadataRecord`, `UserInboxRecord`, and
  `ChatMessageRecord`) with `to_dynamo_item()` factories;
- API models (`Conversation`, `ConversationWithUser`, `ChatMessage`,
  `ConversationPage`, `MessagePage`) and request/event validation models;
- cursor encode/decode helpers that reject malformed cursors with a 400 rather
  than exposing DynamoDB key details.

`ConversationWithUser` should include an existing `UserSearch` for the other
participant, so the client can render username/avatar without adding a request
per inbox row. The service may batch/parallelize existing
`user_service.get_user_by_id` calls while respecting the page limit.

### Service

Add `app/services/chat_service.py` as a module singleton (`chat_service =
ChatService()`). Its public methods should be narrowly typed:

- `get_or_create_direct_conversation(current_user_id, recipient_id)`
- `list_conversations(user_id, limit, cursor)`
- `get_messages(conversation_id, user_id, limit, cursor)`
- `send_message(conversation_id, sender_id, content, client_message_id)`
- `get_conversation_for_member(conversation_id, user_id)` for router/socket
  authorization.

Use `get_item`/`query` for all reads, `TransactWriteItems` for creation and
message writes, and let unexpected `ClientError`s propagate to the global
handler. Convert expected conditions (recipient missing, self chat,
non-member, invalid cursor, duplicate idempotency key) to explicit domain
errors that the HTTP router and WebSocket handler map to safe client errors.
The transaction's idempotency condition is a message item keyed by the client
message id; a retry reads and returns the existing persisted message instead
of creating a duplicate.

### Authentication and connection lifecycle

Add an async `get_current_websocket_user(websocket: WebSocket)` helper to
`app/auth/clerk.py`. It extracts the token, calls the existing
`clerk_auth.verify_token`, checks `sub`, and returns the same user-dictionary
shape as `get_current_user`. It must not use `HTTPBearer`/`Depends`, which are
HTTP-request-specific. Refactor shared claim-to-user-dictionary logic into a
small private helper so HTTP and WebSocket identities cannot drift.

Add `app/services/connection_manager.py`, intentionally stateless with
respect to business data: a process-local, lock-protected
`user_id -> set[WebSocket]` registry with `connect`, `disconnect`, and
best-effort `send_to_users`. Failed sends remove only the failed socket.
There is no DynamoDB connection/presence state in v1.

Add `app/api/chat.py` for REST routes and `app/api/chat_websocket.py` (or the
WebSocket endpoint in `chat.py` if the project prefers one module). The
WebSocket endpoint accepts, registers, reads JSON in a receive loop, validates
the discriminated event, calls `chat_service`, then broadcasts the persisted
event via the connection manager. A `finally` block always unregisters the
socket. Register the REST router under `/api/chats` and the WebSocket route at
`/ws/chat` in `app/main.py`.

### Settings and operational documentation

Add bounded chat settings in `app/core/config.py` (message length and page
limits) with safe defaults. Reuse the configured frontend origins to validate
the WebSocket `Origin` header before accepting a browser connection; CORS
middleware itself does not protect WebSockets. Document optional values in
`.env.example`, add the access patterns and migration note as **Phase 10** in
`project-changes.md`, and update the backend README endpoint/run notes. No
table provisioning or GSI change is expected.

## Frontend design

1. Extend `frontend/src/types/index.ts` with the REST models and WebSocket
   event unions exactly matching `app/models/chat.py`.
2. Add `frontend/src/services/chatService.ts` following the existing
   `useChatService()` pattern. It owns TanStack Query keys for inbox,
   conversation, and paged history; REST mutations use `useApi()` and
   invalidate/update only the relevant keys.
3. Add a dedicated `frontend/src/services/chatSocket.ts` or `useChatSocket`
   hook. It obtains a fresh Clerk token inside the connection routine, derives
   `ws://`/`wss://` from `VITE_API_BASE_URL` (with an optional
   `VITE_WS_BASE_URL` override), reconnects with bounded exponential backoff,
   and closes on unmount/sign-out. It must not create a new socket on every
   component render. Incoming events update the TanStack Query cache; no
   server data goes into Zustand.
4. Add `Chat.tsx` and `Chats.tsx` pages plus focused reusable components for
   the inbox, message list, composer, and connection state. Use Tailwind,
   `react-hook-form`/Zod for the composer, `date-fns` for timestamps, and
   optimistic pending messages keyed by `client_message_id`.
5. Register `/chats` and `/chats/:conversationId` in `frontend/src/App.tsx`,
   add a Chats navigation item in `components/Layout.tsx`, and add a Message
   action on another user's profile that opens the direct conversation then
   navigates to it. Do not allow a message action for the current user.
6. Update `frontend/.env.example` and frontend README only if a dedicated
   WebSocket base URL is introduced. Otherwise document that it derives from
   the existing API base URL.

## Affected files

| File | Planned change |
| --- | --- |
| `app/models/chat.py` | New chat records, public models, validation events, key/cursor helpers. |
| `app/services/chat_service.py` | New durable direct-message, inbox, membership, and transaction logic. |
| `app/services/connection_manager.py` | New in-process multi-tab WebSocket registry and fan-out. |
| `app/auth/clerk.py` | Shared identity mapping and WebSocket Clerk-token verification. |
| `app/api/chat.py` | New authenticated REST inbox/direct-conversation/history routes. |
| `app/api/chat_websocket.py` | New authenticated `/ws/chat` protocol endpoint and lifecycle handling. |
| `app/main.py` | Register the chat routes; preserve existing middleware/handlers. |
| `app/core/config.py`, `.env.example` | Bounded chat settings and allowed-origin configuration/documentation. |
| `project-changes.md`, `README.md` | Phase 10 schema/access-pattern/migration and endpoint documentation. |
| `tests/test_chat.py` | New REST, persistence, security, idempotency, and WebSocket tests. |
| `tests/conftest.py` | Only if required to provide a clean WebSocket auth mock or fully paginated table cleanup. |
| `frontend/src/types/index.ts` | Matching chat API/event contracts. |
| `frontend/src/services/chatService.ts`, `frontend/src/services/chatSocket.ts` | New query/mutation and WebSocket lifecycle/cache integration. |
| `frontend/src/pages/Chats.tsx`, `frontend/src/pages/Chat.tsx` | New inbox and active-conversation screens. |
| `frontend/src/components/chat/*` | New presentation-only inbox, message list, composer, and status components. |
| `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/pages/Profile.tsx` | Chat routes, navigation, and direct-message entry point. |
| `frontend/.env.example`, `frontend/README.md` | Only if a WebSocket URL override is exposed. |

No existing post, user, follow, like, comment, upload, database setup, or
GSI implementation should be modified for the feature.

## Implementation phases

1. **Contract and storage foundation** — add chat models/key helpers, service
   skeleton, direct-conversation creation, inbox/history queries, transactions,
   and model/service tests. Confirm the DynamoDB access-pattern table before
   wiring a UI.
2. **HTTP API and authorization** — add chat router routes, explicit domain
   error mapping, membership tests, cursor tests, and Phase 10 documentation.
3. **WebSocket transport** — add WebSocket Clerk verification, origin checks,
   connection manager, validated event protocol, persistence-before-broadcast,
   disconnect handling, and socket tests.
4. **Frontend data layer** — add shared types, chat REST hooks, singleton
   socket lifecycle, optimistic reconciliation, cache updates, and reconnection
   behavior.
5. **Frontend experience** — add inbox/conversation views, routing/navigation,
   profile entry point, loading/empty/error/offline states, and responsive
   Tailwind layout.
6. **Verification and release readiness** — run backend tests and frontend
   typecheck/lint/build; manually test two independently signed-in browsers
   against local DynamoDB, reconnect/offline history, token expiry, and the
   Docker WebSocket upgrade path. Keep production at one worker until the
   scale-out design is approved.

## Testing strategy and acceptance criteria

### Backend automated tests

- Direct conversation creation is deterministic, idempotent under a simulated
  concurrent request, rejects self/nonexistent recipients, and stores exactly
  one metadata item plus two inbox projections.
- Inbox listing uses a `Query` on `USER#{id}`/`CHAT#`, is reverse
  chronological, resolves the other user's `UserSearch`, honors its cursor,
  and never leaks conversations to a third user.
- Message history requires membership, returns chronological pages without
  duplicates/gaps, and rejects malformed or cross-conversation cursors.
- Sending persists a message and atomically refreshes both inbox projections;
  a repeated `client_message_id` returns the original message without a second
  write.
- WebSocket tests cover rejected missing/invalid token and origin, successful
  connection, invalid event validation, sender/recipient event receipt,
  two-tabs-for-one-user fan-out, unauthorized conversation send, and cleanup
  after disconnect. Mock `clerk_auth.verify_token` rather than weakening the
  production verifier.
- Run the established suite: `python -m pytest tests/ -v` with DynamoDB Local.

### Frontend verification

- `npm run build` and `npm run lint` pass with TypeScript contracts aligned to
  backend Pydantic responses/events.
- Manual two-user flow: open a profile, start a direct conversation, exchange
  messages in real time, refresh each page, and observe full history/inbox
  ordering.
- Exercise multiple tabs for the same account, recipient offline then online,
  reconnect after an intentional socket close, invalid/expired auth, empty
  inbox/history, and mobile navigation.

### Completion criteria

Chat is ready only when durable history works after refresh, messages are
visible in real time to all connected participant tabs, non-participants
cannot read/send/connect to a conversation, no message duplication occurs on
retry, and all existing backend tests plus the frontend build/lint remain
green.

## Approval gate

This document is a plan only. No application source has been changed. Begin
Phase 1 only after explicit approval, and confirm the one-to-one-only scope
before extending it to group chat or production multi-worker fan-out.
