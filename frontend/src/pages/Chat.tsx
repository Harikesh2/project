import { useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Loader2, ArrowLeft, MessageSquare } from 'lucide-react';

import { ChatProvider, useChat } from '@/context/ChatContext';
import { ChatMessage } from '@/types';
import MessageComposer from '@/components/chat/MessageComposer';
import ChatMessageComponent from '@/components/chat/ChatMessage';

export default function Chat() {
  const { conversationId } = useParams<{ conversationId: string }>();
  if (!conversationId) return null;
  return (
    <ChatProvider conversationId={conversationId}>
      <ChatView />
    </ChatProvider>
  );
}

function ChatView() {
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    recipient,
    isLoadingRecipient,
    messages,
    isLoadingMessages,
    messagesError,
    isNotFound,
    sendMessage,
    currentUserId,
    isConnected,
  } = useChat();

  // Auto-scroll to the newest message whenever the thread grows.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  if (isLoadingRecipient || isLoadingMessages) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (messagesError && !isNotFound) {
    return (
      <div className="flex items-center justify-center h-full text-red-500 text-sm">
        Failed to load messages. Please try again.
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col h-[calc(100vh-12rem)]">
      <div className="flex items-center gap-3 p-3 border-b border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-t-xl">
        <button
          onClick={() => navigate('/chats')}
          className="p-1 hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-slate-400" />
        </button>
        {recipient ? (
          <Link to={`/profile/${recipient.user_id}`} className="flex items-center gap-3">
            <div className="avatar avatar-sm border border-gray-200 dark:border-slate-700">
              {recipient.avatar_url ? (
                <img
                  src={recipient.avatar_url}
                  alt={recipient.username}
                  className="w-full h-full object-cover rounded-full"
                />
              ) : (
                <span className="text-gray-600 dark:text-gray-400">
                  {recipient.username[0]?.toUpperCase() || '?'}
                </span>
              )}
            </div>
            <p className="font-semibold text-gray-900 dark:text-white">
              {recipient.username}
            </p>
          </Link>
        ) : (
          <>
            <div className="avatar avatar-sm border border-gray-200 dark:border-slate-700">
              <span className="text-gray-600 dark:text-gray-400">?</span>
            </div>
            <p className="font-semibold text-gray-900 dark:text-white">Conversation</p>
          </>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50 dark:bg-slate-900">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <MessageSquare className="w-12 h-12 mx-auto text-gray-400 dark:text-slate-500 mb-4" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              No messages yet. Start the conversation!
            </h2>
            <p className="text-gray-600 dark:text-slate-400 text-sm">
              Say hello by typing a message below.
            </p>
          </div>
        ) : (
          messages.map((msg: ChatMessage) => (
            <ChatMessageComponent
              key={msg.message_id}
              msg={msg}
              currentUserId={currentUserId}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <MessageComposer onSend={sendMessage} isConnected={isConnected} />
    </div>
  );
}
