import { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';

const MAX_LENGTH = 5000;

interface MessageComposerProps {
  onSend: (content: string, clientMessageId: string) => void;
  disabled?: boolean;
  // Drives the status pill + Send-button gate. Defaults to true so the
  // composer remains usable if a caller forgets to pass it.
  isConnected?: boolean;
}

export default function MessageComposer({
  onSend,
  disabled,
  isConnected = true,
}: MessageComposerProps) {
  const [text, setText] = useState('');

  // Send is blocked if the caller disabled us, the box is empty, OR the
  // socket is offline. When the socket is down, ChatSocket's outbox will
  // buffer the message on reconnect, but blocking here keeps the UX
  // honest: the user sees a clear "offline" pill instead of a bubble
  // that may sit pending for a long time.
  const canSend = !!text.trim() && !disabled && isConnected;

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!canSend) return;
    const clientMessageId = crypto.randomUUID();
    onSend(text.trim(), clientMessageId);
    setText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-2 p-3 border-t border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900"
    >
      <div className="flex-1 relative">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isConnected ? 'Type a message...' : 'Reconnecting…'}
          maxLength={MAX_LENGTH}
          rows={1}
          className="textarea min-h-[40px] max-h-[120px] resize-none pr-16"
        />
        <span className="absolute bottom-2 right-3 text-xs text-gray-400 dark:text-slate-500">
          {text.length}/{MAX_LENGTH}
        </span>
      </div>
      <button
        type="submit"
        disabled={!canSend}
        title={isConnected ? 'Send' : 'Offline — message will not be queued'}
        className="btn btn-primary btn-sm flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Send className="w-4 h-4" />
      </button>
      <ConnectionPill isConnected={isConnected} />
    </form>
  );
}

// Small status pill in the composer footer. Two states:
//   - online  → nothing rendered (keeps the footer clean)
//   - offline → subtle yellow/amber pill with a spinner icon
//     (matches the rest of the dark/light theme via existing utilities)
function ConnectionPill({ isConnected }: { isConnected: boolean }) {
  if (isConnected) return null;
  return (
    <span
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
    >
      <Loader2 className="w-3 h-3 animate-spin" />
      Connecting…
    </span>
  );
}
