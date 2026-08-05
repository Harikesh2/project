import { ChatSendEvent, ChatWsEvent, NotificationWsEvent } from '@/types';

// Coarse lifecycle states. Subscribers (e.g. ChatContext → MessageComposer) use
// this to render "Connecting…" / "Offline" pills and to gate interactive
// controls. 'idle' is the post-disconnect, pre-connect state. 'connecting'
// covers both the initial handshake and exponential-backoff retries.
export type ConnectionState = 'idle' | 'connecting' | 'open' | 'closed';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function getWsUrl(path: string): string {
  const scheme = API_BASE_URL.startsWith('https://') ? 'wss' : 'ws';
  return `${API_BASE_URL.replace(/^https?/, scheme)}${path}`;
}

async function getToken(): Promise<string | null> {
  if (window.Clerk) {
    try {
      return (await window.Clerk.session?.getToken()) || null;
    } catch {
      return null;
    }
  }
  const demoToken = localStorage.getItem('demo_token');
  return demoToken === 'demo_token_123' ? demoToken : null;
}

export interface ReconnectingSocketConfig<TOut> {
  path: string;
  // Chat-specific: buffer outgoing events while the socket is down and drain
  // them on reopen. When the buffer is full the oldest event is dropped and
  // onOverflow is called with it.
  outbox?: boolean;
  onOverflow?: (dropped: TOut) => void;
}

export class ReconnectingSocket<TIn, TOut> {
  private ws: WebSocket | null = null;
  private listeners = new Set<(event: TIn) => void>();
  private connectionListeners = new Set<(state: ConnectionState) => void>();
  private state: ConnectionState = 'idle';
  private shouldReconnect = false;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private outbox: TOut[] = [];
  private static readonly MAX_OUTBOX = 100;

  constructor(private readonly config: ReconnectingSocketConfig<TOut>) {}

  private setState(next: ConnectionState): void {
    if (this.state === next) return;
    this.state = next;
    for (const cb of this.connectionListeners) cb(next);
  }

  private get backoffDelay(): number {
    return Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000) + Math.random() * 1000;
  }

  subscribe(cb: (event: TIn) => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  subscribeConnection(cb: (state: ConnectionState) => void): () => void {
    this.connectionListeners.add(cb);
    // Fire the current state immediately so subscribers don't have to wait
    // for the next transition to render anything.
    cb(this.state);
    return () => this.connectionListeners.delete(cb);
  }

  dispatch(event: TIn): void {
    for (const cb of this.listeners) cb(event);
  }

  async connect(): Promise<void> {
    // Idempotent: global + page-level callers both connect; don't churn an
    // already-open (or in-flight) socket.
    if (this.state === 'open' || this.state === 'connecting') return;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    await this.doConnect();
  }

  private async doConnect(): Promise<void> {
    this.disconnect();

    const token = await getToken();
    if (!token) {
      this.setState(this.shouldReconnect ? 'connecting' : 'closed');
      this.scheduleReconnect();
      return;
    }

    const url = `${getWsUrl(this.config.path)}?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(url);
    this.setState('connecting');

    this.ws.onopen = () => {
      this.setState('open');
      this.reconnectAttempts = 0;
      // Drain any events that were queued while the socket was connecting.
      if (this.config.outbox) {
        const pending = this.outbox;
        this.outbox = [];
        for (const ev of pending) {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(ev));
          }
        }
      }
    };

    this.ws.onmessage = (event) => {
      try {
        this.dispatch(JSON.parse(event.data) as TIn);
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      if (this.shouldReconnect) {
        this.setState('connecting');
        this.scheduleReconnect();
      } else {
        this.setState('closed');
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect) return;
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => this.doConnect(), this.backoffDelay);
  }

  send(event: TOut): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(event));
      return;
    }
    if (!this.config.outbox) return;
    // Socket isn't open yet (e.g. user hit Enter within the first ~100ms of
    // navigation, before onopen fires). Queue the event; onopen will drain.
    if (this.outbox.length >= ReconnectingSocket.MAX_OUTBOX) {
      // Drop the oldest to make room, and surface a toast-equivalent so the
      // user has a chance to notice the queue is overwhelmed.
      this.outbox.shift();
      this.config.onOverflow?.(event);
    }
    this.outbox.push(event);
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.setState('closed');
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const chatSocket = new ReconnectingSocket<ChatWsEvent, ChatSendEvent>({
  path: '/ws/chat',
  outbox: true,
  onOverflow: () =>
    chatSocket.dispatch({
      type: 'error',
      code: 'SEND_FAILED',
      detail: 'Send queue full; oldest message dropped',
    }),
});

export const notificationSocket = new ReconnectingSocket<NotificationWsEvent, never>({
  path: '/ws/notifications',
});
