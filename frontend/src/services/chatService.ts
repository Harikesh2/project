import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from './api';
import { Conversation, InboxItem, ChatMessage, CursorPage } from '@/types';
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
  };
};
