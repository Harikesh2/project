import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, Loader2, CheckCheck, Heart, UserPlus, MessageCircle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import { useNotificationService } from '@/services/notificationService';
import { Notification as NotificationType } from '@/types';

const typeIcons: Record<string, typeof Heart> = {
  like: Heart,
  follow: UserPlus,
  comment: MessageCircle,
};

const typeColors: Record<string, string> = {
  like: 'text-red-500',
  follow: 'text-blue-500',
  comment: 'text-green-500',
};

function NotifIcon({ type }: { type: string }) {
  const Icon = typeIcons[type] || Bell;
  const color = typeColors[type] || 'text-gray-500';
  return (
    <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${color} bg-opacity-10 bg-current`}>
      <Icon className="w-5 h-5" />
    </div>
  );
}

function NotificationRow({ notif }: { notif: NotificationType }) {
  const isUnread = !notif.read_at;
  const detailLink = notif.type === 'follow'
    ? `/profile/${notif.actor_id}`
    : `/posts/${notif.entity_id}`;

  const text = (() => {
    const actor = notif.payload.actor_username;
    switch (notif.type) {
      case 'like':
        return <>{actor} liked your post{notif.payload.preview && <span className="block text-sm text-gray-400 truncate">"{notif.payload.preview}"</span>}</>;
      case 'follow':
        return <>{actor} started following you</>;
      case 'comment':
        return <>{actor} commented: <span className="text-gray-400">"{notif.payload.preview}"</span></>;
      default:
        return <>New notification</>;
    }
  })();

  return (
    <Link
      to={detailLink}
      className={`flex items-start gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
        isUnread ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-blue-500' : ''
      }`}
    >
      <NotifIcon type={notif.type} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-900 dark:text-gray-100">{text}</p>
        <p className="text-xs text-gray-500 mt-1">
          {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true })}
        </p>
      </div>
    </Link>
  );
}

export default function Notifications() {
  const { useNotifications, useMarkAllAsRead } = useNotificationService();
  const [pageKeys, setPageKeys] = useState<string[]>([]);
  const [accumulated, setAccumulated] = useState<NotificationType[]>([]);
  const nextKey = pageKeys[pageKeys.length - 1];
  const { data, isLoading, isFetching } = useNotifications(20, nextKey);

  // Accumulate pages
  useEffect(() => {
    if (!data) return;
    if (pageKeys.length === 0) {
      // First page
      setAccumulated(data.items);
    } else if (data.items.length > 0) {
      setAccumulated((prev) => {
        const existing = new Set(prev.map((n) => n.id));
        const fresh = data.items.filter((n) => !existing.has(n.id));
        return fresh.length ? [...prev, ...fresh] : prev;
      });
    }
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleLoadMore = () => {
    if (data?.next_token) {
      setPageKeys((prev) => [...prev, data.next_token!]);
    }
  };

  const { mutate: markAllAsRead, isPending: markingAll } = useMarkAllAsRead();

  const hasMore = !!data?.next_token;

  if (isLoading && accumulated.length === 0) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <div className="flex items-center space-x-3 mb-6">
          <Bell className="w-6 h-6 text-primary-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Notifications</h1>
        </div>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="flex items-center justify-between mb-6 px-4">
        <div className="flex items-center space-x-3">
          <Bell className="w-6 h-6 text-primary-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Notifications</h1>
        </div>
        {accumulated.length > 0 && accumulated.some((n) => !n.read_at) && (
          <button
            onClick={() => markAllAsRead()}
            disabled={markingAll}
            className="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-700 disabled:opacity-50"
          >
            <CheckCheck className="w-4 h-4" />
            {markingAll ? 'Marking...' : 'Mark all read'}
          </button>
        )}
      </div>

      {!isLoading && accumulated.length === 0 ? (
        <div className="text-center py-16">
          <Bell className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
          <p className="text-gray-500 dark:text-gray-400">No notifications yet.</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-100 dark:divide-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          {accumulated.map((notif) => (
            <NotificationRow key={notif.id} notif={notif} />
          ))}
        </div>
      )}

      {hasMore && !isLoading && (
        <div className="text-center mt-6">
          <button
            onClick={handleLoadMore}
            disabled={isFetching}
            className="btn btn-secondary"
          >
            {isFetching ? (
              <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
            ) : null}
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
