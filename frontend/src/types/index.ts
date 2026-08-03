// User types — API contract (maps to DynamoDB METADATA + PROFILE items on backend)
// DynamoDB keys: PK=USER#{user_id}, SK=METADATA (core) | PROFILE (avatar_url, bio)
// GSI1: EMAIL#{email}/USER  |  GSI2: USERNAME#{username}/USER
export interface User {
  user_id: string;
  username: string;
  email: string;
  avatar_url?: string;
  bio?: string;
  created_at: string;
  updated_at: string;
  followers_count: number;
  following_count: number;
  posts_count: number;
}

export interface UserProfile extends User {
  is_following?: boolean;
  is_followed_by?: boolean;
}

export interface UserSearch {
  user_id: string;
  username: string;
  avatar_url?: string;
  bio?: string;
  followers_count: number;
}

export interface UserCreate {
  username: string;
  email: string;
  avatar_url?: string;
  bio?: string;
}

export interface UserUpdate {
  username?: string;
  avatar_url?: string;
  bio?: string;
}

// Post types — API contract (maps to DynamoDB METADATA + timeline duplicate on backend)
// Canonical: PK=POST#{post_id}, SK=METADATA  |  Timeline: PK=USER#{user_id}, SK=POST#{post_id}
// GSI3: POSTS / created_at (global feed)
export interface Post {
  post_id: string;
  user_id: string;
  content: string;
  image_url?: string;
  created_at: string;
  updated_at: string;
  likes_count: number;
  comments_count: number;
}

export interface PostWithUser extends Post {
  user: UserSearch;
  is_liked?: boolean;
}

export interface PostCreate {
  content: string;
  image_url?: string;
}

export interface PostUpdate {
  content?: string;
  image_url?: string;
}

// Comment types — API contract (maps to DynamoDB canonical + user duplicate on backend)
// Canonical: PK=POST#{post_id}, SK=COMMENT#{comment_id}
// User activity: PK=USER#{user_id}, SK=COMMENT#{comment_id}
export interface Comment {
  comment_id: string;
  post_id: string;
  user_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface CommentWithUser extends Comment {
  user: UserSearch;
}

export interface CommentCreate {
  content: string;
}

// Follow types — API contract (maps to duplicated relationship items on backend)
// Following: PK=USER#{follower_id}, SK=FOLLOWING#{target_id}
// Followers: PK=USER#{target_id}, SK=FOLLOWER#{follower_id}
export interface Follow {
  follower_id: string;
  following_id: string;
  created_at: string;
}

export interface FollowWithUser extends Follow {
  user: UserSearch;
}

// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  has_more: boolean;
  last_key?: string;
}

// Form types
export interface LoginForm {
  email: string;
  password: string;
}

export interface SignUpForm {
  email: string;
  password: string;
  username: string;
}

export interface PostForm {
  content: string;
  image_url?: string;
}

export interface CommentForm {
  content: string;
}

export interface ProfileForm {
  username: string;
  bio?: string;
  avatar_url?: string;
}

// Chat types — matches backend ConversationMetadataRecord
export interface Conversation {
  conversation_id: string;
  participant_ids: string[];
  created_at: string;
  updated_at: string;
  last_message_preview?: string;
  last_message_at?: string;
}

// Chat inbox item — matches backend ConversationWithUser
// (enriched by list_conversations: metadata + the other participant's
// public profile, so the inbox row can render without a follow-up call).
export interface InboxItem {
  conversation_id: string;
  participant_ids: string[];
  created_at: string;
  updated_at: string;
  last_message_preview?: string;
  last_message_at?: string;
  other_user: UserSearch;
}

// Chat message — matches backend ChatMessageRecord
export interface ChatMessage {
  message_id: string;
  sender_id: string;
  content: string;
  created_at: string;
  client_message_id: string;
}

// Chat paginated response (backend returns next_cursor instead of last_key/has_more)
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

// WebSocket event — outgoing message.send
export interface ChatSendEvent {
  type: "message.send";
  conversation_id: string;
  client_message_id: string;
  content: string;
}

// WebSocket event — incoming message.created
export interface ChatMessageCreatedEvent {
  type: "message.created";
  conversation: Conversation;
  message: ChatMessage;
  client_message_id: string;
}

// WebSocket event — incoming ready
export interface ChatReadyEvent {
  type: "ready";
}

// WebSocket event — incoming error. `client_message_id` is echoed back on
// `SEND_FAILED` / `INVALID_EVENT` so the client can target the exact failing
// optimistic bubble; it's omitted for connection-level / global errors.
export interface ChatErrorEvent {
  type: "error";
  code: string;
  detail: string;
  client_message_id?: string;
}

// Union type for all incoming WebSocket events
export type ChatWsEvent = ChatReadyEvent | ChatMessageCreatedEvent | ChatErrorEvent;

// Notification types — matches backend Notification API response
// DynamoDB: PK=NOTIFICATION#{id}, SK=METADATA (canonical)
//           PK=USER#{recipient_id}, SK=NOTIFICATION#{created_at}#{id} (user list)
export type NotificationType = "like" | "follow" | "comment";

export interface Notification {
  id: string;
  recipient_id: string;
  actor_id: string;
  type: NotificationType;
  entity_id: string;
  entity_type: string;
  payload: {
    actor_username: string;
    actor_avatar_url?: string;
    preview?: string;
  };
  created_at: string;
  read_at: string | null;
}

export interface NotificationListResponse {
  items: Notification[];
  next_token: string | null;
}

export interface UnreadCountResponse {
  count: number;
}

// WebSocket event — incoming notification.created
export interface NotificationCreatedEvent {
  type: "notification.created";
  notification: Notification;
}

// Union type for all notification WebSocket events
export type NotificationWsEvent = NotificationCreatedEvent;