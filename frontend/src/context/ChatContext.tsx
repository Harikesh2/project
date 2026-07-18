import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';

import { useChatService } from '@/services/chatService';
import { useUserService } from '@/services/userService';
import { chatSocket } from '@/services/chatSocket';
import { ChatMessage } from '@/types';

export interface ChatRecipient {
  user_id: string;
  username: string;
  avatar_url: string | null;
}

interface ChatContextValue {
  // Phase 1 — recipient (header) resolution
  conversationId: string;
  recipient: ChatRecipient | null;
  isLoadingRecipient: boolean;
  recipientError: Error | null;

  // Phase 2 — message thread + send
  messages: ChatMessage[];
  isLoadingMessages: boolean;
  messagesError: Error | null;
  isNotFound: boolean;
  sendMessage: (content: string, clientMessageId: string) => void;
  currentUserId: string | undefined;
  sendError: string | null;

  // Socket lifecycle — drives the composer status pill + Send-button gate.
  isConnected: boolean;
}

const ChatContext = createContext<ChatContextValue | null>(null);

interface ChatProviderProps {
  conversationId: string;
  children: ReactNode;
}

// ChatProvider owns recipient (header) resolution AND the message thread for
// a single conversation view. Socket lifecycle and optimistic send logic are
// colocated with the state they mutate.
//
// Resolution cascade (priority order):
//   1. ?with= search param  → use as other_user_id hint
//   2. /chats/{id} response → use other_user_id if backend exposes it
//   3. /users/{id} profile  → fetch the rich metadata we actually need
//   4. None of the above    → recipient stays null, header shows fallback
export function ChatProvider({ conversationId, children }: ChatProviderProps) {
  const [searchParams] = useSearchParams();
  const { useConversation, useMessages } = useChatService();
  const { useUserProfile, useCurrentUser } = useUserService();

  // 1) ?with= hint, if present
  const withHint = searchParams.get('with') ?? '';

  // 2) Conversation record — currently the backend Conversation type only has
  //    participant_ids, but we read defensively so the cascade lights up the
  //    day the backend starts returning other_user_id / other_username /
  //    other_avatar_url.
  const {
    data: conversation,
    isLoading: isLoadingConversation,
    error: conversationError,
  } = useConversation(conversationId);

  // Priority: ?with= > conversation.other_user_id > empty (skip profile fetch).
  const resolvedUserId =
    withHint || (conversation?.other_user_id ?? '');

  // 3) The chat record may already include rich recipient metadata. If so,
  //    skip the profile fetch to avoid a redundant round-trip. Today this
  //    branch is always false; it activates when the backend is extended.
  const chatHasRichMetadata = Boolean(
    conversation &&
      (conversation as { other_username?: string }).other_username &&
      (conversation as { other_avatar_url?: string | null }).other_avatar_url !== undefined,
  );

  const {
    data: profile,
    isLoading: isLoadingProfile,
    error: profileError,
  } = useUserProfile(chatHasRichMetadata ? '' : resolvedUserId);

  const recipient: ChatRecipient | null = useMemo(() => {
    if (chatHasRichMetadata && conversation) {
      return {
        user_id: resolvedUserId,
        username: (conversation as { other_username?: string }).other_username!,
        avatar_url:
          (conversation as { other_avatar_url?: string | null }).other_avatar_url ?? null,
      };
    }
    if (profile) {
      return {
        user_id: profile.user_id,
        username: profile.username,
        avatar_url: profile.avatar_url ?? null,
      };
    }
    return null;
  }, [chatHasRichMetadata, conversation, profile, resolvedUserId]);

  const isLoadingRecipient =
    isLoadingConversation || (!!resolvedUserId && isLoadingProfile);
  const recipientError =
    (conversationError as Error | null) ?? (profileError as Error | null);

  // --- Phase 2: message thread + send -------------------------------------

  const { data: currentUser } = useCurrentUser();
  const currentUserId = currentUser?.user_id;

  const {
    data: messagesPage,
    isLoading: isLoadingMessages,
    error: messagesErrorRaw,
  } = useMessages(conversationId);

  // 404 on messages endpoint → empty state (not a hard error). Matches the
  // guard Chat.tsx had before Phase 2 moved it into the provider.
  const isNotFound =
    !!messagesErrorRaw &&
    (messagesErrorRaw as { response?: { status?: number } })?.response?.status === 404;

  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
  const [sendError, setSendError] = useState<string | null>(null);
  // Optimistic default: assume the socket is up until told otherwise. The
  // subscribeConnection callback below will correct this on the next state
  // change (or immediately, since it fires with the current state on attach).
  const [isConnected, setIsConnected] = useState<boolean>(true);

  // Sync fetched history into local state.
  useEffect(() => {
    if (messagesPage?.items) {
      setLocalMessages(messagesPage.items);
    }
  }, [messagesPage]);

  // Wire up the WebSocket for incoming messages + send failures.
  useEffect(() => {
    chatSocket.connect();
    const unsub = chatSocket.subscribe((event) => {
      if (event.type === 'message.created') {
        setLocalMessages((prev) =>
          prev.map((m) =>
            m.client_message_id === event.client_message_id ? event.message : m,
          ),
        );
      }
      if (event.type === 'error' && event.code === 'SEND_FAILED') {
        const detail = event.detail || 'Failed to send message';
        setSendError(detail);
        toast.error(detail);
        // Drop the matching optimistic bubble. If the backend echoed the
        // client_message_id, target that one exactly; otherwise fall back
        // to the most recent pending bubble (best-effort — the user may
        // have several in flight, in submit order).
        const target = event.client_message_id;
        setLocalMessages((prev) =>
          target
            ? prev.filter((m) => m.client_message_id !== target)
            : removeMostRecentPending(prev),
        );
      }
    });
    return unsub;
  }, []);

  // Mirror the socket's lifecycle into context so children (MessageComposer)
  // can render a status pill and gate the Send button without each one
  // subscribing to chatSocket directly.
  useEffect(() => {
    return chatSocket.subscribeConnection((state) => {
      setIsConnected(state === 'open');
    });
  }, []);

  // A "pending" bubble is an optimistic one: its `message_id` still equals
  // its `client_message_id`. Once the server persists a message, it gets a
  // distinct `message_id` and the bubble is no longer pending. Returns a
  // new list with the most recent pending bubble removed.
  const removeMostRecentPending = (msgs: ChatMessage[]): ChatMessage[] => {
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].message_id === msgs[i].client_message_id) {
        return msgs.filter((_, idx) => idx !== i);
      }
    }
    return msgs;
  };

  const sendMessage = (content: string, clientMessageId: string) => {
    if (!currentUserId) {
      // Defensive: the loading guard in ChatView prevents this from firing
      // before the current user is known, but bail rather than emit a message
      // with an unknown sender_id.
      return;
    }
    const optimistic: ChatMessage = {
      message_id: clientMessageId,
      sender_id: currentUserId,
      content,
      created_at: new Date().toISOString(),
      client_message_id: clientMessageId,
    };
    setLocalMessages((prev) => [...prev, optimistic]);
    chatSocket.send({
      type: 'message.send',
      conversation_id: conversationId,
      client_message_id: clientMessageId,
      content,
    });
  };

  const value: ChatContextValue = {
    conversationId,
    recipient,
    isLoadingRecipient,
    recipientError,

    messages: localMessages,
    isLoadingMessages: isLoadingMessages && !isNotFound,
    messagesError: (messagesErrorRaw as Error | null) && !isNotFound
      ? (messagesErrorRaw as Error)
      : null,
    isNotFound,
    sendMessage,
    currentUserId,
    sendError,
    isConnected,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return ctx;
}
