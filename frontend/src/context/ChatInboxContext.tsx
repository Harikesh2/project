import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';

import { useChatService } from '@/services/chatService';
import { chatSocket } from '@/services/reconnectingSocket';
import { useQueryClient } from '@tanstack/react-query';
import { InboxItem } from '@/types';

// Inbox list lives in its own context, mounted page-level by Chats.tsx.
// Kept separate from ChatContext so the inbox view doesn't drag in the
// socket / message-thread concerns (and vice versa). Symmetric to the
// per-route provider pattern from Phases 1-2.
//
// Phase 3 (revised): the backend list_conversations endpoint now returns
// enriched rows (other_user.username, other_avatar_url, last_message_*),
// so each row carries everything it needs to render. No per-row
// useUserProfile fan-out required — the inbox renders from the row
// directly. Future inbox concerns (auto-refresh on socket events,
// filter/search, unread badges) can extend this context without
// touching Chats.tsx.
interface ChatInboxContextValue {
  conversations: InboxItem[];
  isLoadingInbox: boolean;
  inboxError: Error | null;
  isEmpty: boolean;
}

const ChatInboxContext = createContext<ChatInboxContextValue | null>(null);

interface ChatInboxProviderProps {
  children: ReactNode;
}

export function ChatInboxProvider({ children }: ChatInboxProviderProps) {
  const { useConversations } = useChatService();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useConversations();

  useEffect(() => {
    chatSocket.connect();
    return chatSocket.subscribe((event) => {
      if (event.type === 'message.created') {
        queryClient.invalidateQueries({ queryKey: ['chats'] });
      }
    });
  }, [queryClient]);

  const conversations = data?.items ?? [];
  const isEmpty = !isLoading && conversations.length === 0;

  const contextValue: ChatInboxContextValue = useMemo(
    () => ({
      conversations,
      isLoadingInbox: isLoading,
      inboxError: (error as Error | null) ?? null,
      isEmpty,
    }),
    [conversations, isLoading, error, isEmpty],
  );

  return (
    <ChatInboxContext.Provider value={contextValue}>
      {children}
    </ChatInboxContext.Provider>
  );
}

export function useChatInbox(): ChatInboxContextValue {
  const ctx = useContext(ChatInboxContext);
  if (!ctx) {
    throw new Error('useChatInbox must be used within a ChatInboxProvider');
  }
  return ctx;
}
