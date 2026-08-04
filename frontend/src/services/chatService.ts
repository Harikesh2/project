import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from './api';
import { Conversation, InboxItem, ChatMessage, CursorPage, UnreadCountResponse } from '@/types';
import { chatSocket } from './reconnectingSocket';
import toast from 'react-hot-toast';

export const useChatService = () => {
  const api = useApi();
  const queryClient = useQueryClient();

  const useOpenConversation = () => {
    return useMutation({
      mutationFn: async (recipientId: string): Promise<Conversation> => {
        const response = await api.post(`/chats/direct/${recipientId}`);
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['chats'] });
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to open conversation');
      },
    });
  };

  const useConversations = () => {
    return useQuery({
      queryKey: ['chats'],
      queryFn: async (): Promise<CursorPage<InboxItem>> => {
        const response = await api.get('/chats');
        return response.data;
      },
    });
  };

  const useMessages = (conversationId: string) => {
    return useQuery({
      queryKey: ['chats', conversationId, 'messages'],
      queryFn: async (): Promise<CursorPage<ChatMessage>> => {
        const response = await api.get(`/chats/${conversationId}/messages`);
        return response.data;
      },
      enabled: !!conversationId && conversationId !== 'undefined',
    });
  };

  // Total unread messages across all conversations (global badge count).
  const useChatUnreadCount = () => {
    return useQuery({
      queryKey: ['chats', 'unread-count'],
      queryFn: async (): Promise<UnreadCountResponse> => {
        const response = await api.get('/chats/unread-count');
        return response.data;
      },
      refetchInterval: 30_000, // fallback poll every 30s if WS drops
    });
  };

  // Fetch a single conversation record by ID.
  // Phase 1: the backend Conversation type only carries participant_ids, not
  // other_user_id / other_username / other_avatar_url, so this hook is currently
  // a structural placeholder. Once the backend exposes rich recipient metadata
  // (or we add an inbox-by-id endpoint), ChatContext will start using it and
  // drop the redundant useUserProfile round-trip.
  const useConversation = (conversationId: string) => {
    return useQuery({
      queryKey: ['chats', conversationId],
      queryFn: async (): Promise<Conversation> => {
        const response = await api.get(`/chats/${conversationId}`);
        return response.data;
      },
      enabled: !!conversationId && conversationId !== 'undefined',
      retry: false,
    });
  };

  return {
    useOpenConversation,
    useConversations,
    useMessages,
    useConversation,
    useChatUnreadCount,
  };
};

// Standalone hook to subscribe to the chat WS and keep the unread badge fresh.
// Mount once in Layout — it lives for the whole session. Mirrors useNotificationWs.
export const useChatWs = (currentUserId?: string) => {
  const queryClient = useQueryClient();

  const subscribed = useRef(false);

  useEffect(() => {
    if (subscribed.current) return;
    subscribed.current = true;

    chatSocket.connect();

    const unsub = chatSocket.subscribe((event) => {
      // Only count messages from others; our own sends don't bump the badge.
      if (event.type === 'message.created' && event.message.sender_id !== currentUserId) {
        queryClient.setQueryData<UnreadCountResponse>(
          ['chats', 'unread-count'],
          (old) => ({
            count: (old?.count ?? 0) + 1,
          }),
        );
        // Refresh conversation list (reordering) + correct any count drift.
        queryClient.invalidateQueries({ queryKey: ['chats'] });
      }
    });

    return () => {
      unsub();
      chatSocket.disconnect();
      subscribed.current = false;
    };
  }, [queryClient, currentUserId]);
};
