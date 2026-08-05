import { CheckCheck, Loader2 } from 'lucide-react';
import { ChatMessage as ChatMessageType } from '@/types';

interface ChatMessageProps {
  msg: ChatMessageType;
  currentUserId: string | undefined;
}

export default function ChatMessage({ msg, currentUserId }: ChatMessageProps) {
  const isMine = msg.sender_id === currentUserId;
  const isPending = msg.message_id === msg.client_message_id;

  return (
    <div className={`flex ${isMine ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2 ${
          isMine
            ? 'bg-primary-600 text-white rounded-br-md'
            : 'bg-white dark:bg-slate-800 text-gray-900 dark:text-white border border-gray-200 dark:border-slate-700 rounded-bl-md'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap break-words">{msg.content}</p>
        <p className={`text-xs mt-1 flex items-center gap-1 ${isMine ? 'text-primary-200' : 'text-gray-500 dark:text-slate-400'}`}>
          {new Date(msg.created_at).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit' })}
          {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
          {isMine && !isPending && <CheckCheck className="w-3 h-3" />}
        </p>
      </div>
    </div>
  );
}