import { useNavigate } from 'react-router-dom';
import { Loader2, MessageSquare } from 'lucide-react';

import { ChatInboxProvider, useChatInbox } from '@/context/ChatInboxContext';
import { InboxItem } from '@/types';

function InboxRow({ item }: { item: InboxItem }) {
  const navigate = useNavigate();
  const { other_user: otherUser, last_message_preview } = item;

  return (
    <button
      onClick={() => navigate(`/chats/${item.conversation_id}`)}
      className="w-full flex items-center gap-3 p-4 hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors border-b border-gray-100 dark:border-slate-800 text-left"
    >
      <div className="avatar avatar-md shrink-0">
        {otherUser.avatar_url ? (
          <img
            src={otherUser.avatar_url}
            alt={otherUser.username}
            className="w-full h-full object-cover rounded-full"
          />
        ) : (
          <span className="text-gray-600 dark:text-gray-400">
            {otherUser.username?.[0]?.toUpperCase() || '?'}
          </span>
        )}
      </div>
      <div className="flex-1 min-w0">
        <div className="flex items-center justify-between">
          <p className="font-semibold text-gray-900 dark:text-white truncate">
            {otherUser.username}
          </p>
          <span className="text-xs text-gray-500 dark:text-slate-400 shrink-0 ml-2">
            {formatTime(pickTimestamp(item))}
          </span>
        </div>
        <p className="text-sm text-gray-500 dark:text-slate-400 truncate">
          {last_message_preview || 'No messages yet'}
        </p>
      </div>
    </button>
  );
}

// The backend list_conversations enrichment ships both last_message_at and
// updated_at on each row. Prefer last_message_at when present (tracks the
// actual latest message) and fall back to updated_at (always present, also
// bumps for metadata-only changes).
function pickTimestamp(item: InboxItem): string {
  return item.last_message_at ?? item.updated_at;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffDays === 0) {
    return date.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit' });
  }
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return date.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', weekday: 'short' });
  return date.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', month: 'short', day: 'numeric' });
}

function ChatsView() {
  const { conversations, isLoadingInbox, isEmpty } = useChatInbox();

  if (isLoadingInbox) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="max-w-2xl mx-auto text-center py-12">
        <MessageSquare className="w-12 h-12 mx-auto text-gray-400 dark:text-slate-500 mb-4" />
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">No conversations</h2>
        <p className="text-gray-600 dark:text-slate-400">
          Go to a user's profile to send them a message.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 px-1">Messages</h1>
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-800 overflow-hidden">
        {conversations.map((item) => (
          <InboxRow key={item.conversation_id} item={item} />
        ))}
      </div>
    </div>
  );
}

export default function Chats() {
  return (
    <ChatInboxProvider>
      <ChatsView />
    </ChatInboxProvider>
  );
}
