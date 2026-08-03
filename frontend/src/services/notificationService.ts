import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from './api';
import { NotificationListResponse, UnreadCountResponse } from '@/types';
import { notificationSocket } from './notificationSocket';
export const useNotificationService = () => {
  const api = useApi();
  const queryClient = useQueryClient();

  const useNotifications = (limit: number = 20, nextKey?: string) => {
    return useQuery({
      queryKey: ['notifications', { limit, nextKey }],
      queryFn: async (): Promise<NotificationListResponse> => {
        const params: Record<string, string | number> = { limit };
        if (nextKey) params.next_token = nextKey;
        const response = await api.get('/notifications', { params });
        return response.data;
      },
    });
  };

  const useUnreadCount = () => {
    return useQuery({
      queryKey: ['notifications', 'unread-count'],
      queryFn: async (): Promise<UnreadCountResponse> => {
        const response = await api.get('/notifications/unread-count');
        return response.data;
      },
      refetchInterval: 30_000, // fallback poll every 30s if WS drops
    });
  };

  const useMarkAsRead = () => {
    return useMutation({
      mutationFn: async (id: string): Promise<void> => {
        await api.put(`/notifications/${id}/read`);
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
        queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
      },
    });
  };

  const useMarkAllAsRead = () => {
    return useMutation({
      mutationFn: async (): Promise<void> => {
        await api.put('/notifications/read-all');
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
        queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
      },
    });
  };

  return {
    useNotifications,
    useUnreadCount,
    useMarkAsRead,
    useMarkAllAsRead,
  };
};

// Standalone hook to subscribe to the notification WS and keep cache fresh.
// Mount once in Layout — it lives for the whole session.
export const useNotificationWs = () => {
  const queryClient = useQueryClient();

  // Ref to avoid re-subscribing on re-render
  const subscribed = useRef(false);

  useEffect(() => {
    if (subscribed.current) return;
    subscribed.current = true;

    notificationSocket.connect();

    const unsub = notificationSocket.subscribe((event) => {
      if (event.type === 'notification.created') {
        // Prepend to the notification list cache so it shows immediately
        queryClient.setQueryData<NotificationListResponse>(
          ['notifications', { limit: 20, nextKey: undefined }],
          (old) => {
            if (!old) return { items: [event.notification], next_token: null };
            return {
              ...old,
              items: [event.notification, ...old.items],
            };
          },
        );
        // Bump unread count
        queryClient.setQueryData<UnreadCountResponse>(
          ['notifications', 'unread-count'],
          (old) => ({
            count: (old?.count ?? 0) + 1,
          }),
        );
        // Also invalidate to pick up any edge cases
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
        queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
      }
    });

    return () => {
      unsub();
      notificationSocket.disconnect();
      subscribed.current = false;
    };
  }, [queryClient]);
};
