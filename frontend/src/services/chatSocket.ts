import { ChatSendEvent, ChatWsEvent } from '@/types';

type EventCallback = (event: ChatWsEvent) => void;

// Coarse lifecycle states. Subscribers (e.g. ChatContext → MessageComposer) use
// this to render "Connecting…" / "Offline" pills and to gate the Send button.
// 'idle' is the post-disconnect, pre-connect state. 'connecting' covers both
// the initial handshake and exponential-backoff retries.
export type ConnectionState = 'idle' | 'connecting' | 'open' | 'closed';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function getWsBaseUrl(): string {
  if (API_BASE_URL.startsWith('https://')) {
    return API_BASE_URL.replace(/^https/, 'wss') + '/ws/chat';
  }
  return API_BASE_URL.replace(/^http/, 'ws') + '/ws/chat';
}

async function getToken(): Promise<string | null> {
  if (window.Clerk) {
    try {
      return await window.Clerk.session?.getToken() || null;
    } catch {
      return null;
    }
  }
  const demoToken = localStorage.getItem('demo_token');
  return demoToken === 'demo_token_123' ? demoToken : null;
}

class ChatSocketService {
  private ws: WebSocket | null = null;
  private listeners: Set<EventCallback> = new Set();
  private connectionListeners: Set<(state: ConnectionState) => void> = new Set();
  private state: ConnectionState = 'idle';
  private shouldReconnect = false;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  // Buffer of events that arrived before the socket opened (or while it was
  // briefly down). Drained in onopen so sends submitted during the connect
  // race are not silently dropped.
  private outbox: ChatSendEvent[] = [];
  private static readonly MAX_OUTBOX = 100;

  private setState(next: ConnectionState): void {
    if (this.state === next) return;
    this.state = next;
    for (const cb of this.connectionListeners) cb(next);
  }

  private get backoffDelay(): number {
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    return delay + Math.random() * 1000;
  }

  subscribe(cb: EventCallback): () => void {
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

  private notify(event: ChatWsEvent): void {
    this.listeners.forEach(cb => cb(event));
  }

  async connect(): Promise<void> {
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

    const url = `${getWsBaseUrl()}?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(url);
    this.setState('connecting');

    this.ws.onopen = () => {
      this.setState('open');
      this.reconnectAttempts = 0;
      // Drain any events that were queued while the socket was connecting.
      const pending = this.outbox;
      this.outbox = [];
      for (const ev of pending) {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify(ev));
        }
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ChatWsEvent;
        this.notify(data);
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

  send(event: ChatSendEvent): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(event));
      return;
    }
    // Socket isn't open yet (e.g. user hit Enter within the first ~100ms of
    // navigation, before onopen fires). Queue the event; onopen will drain.
    if (this.outbox.length >= ChatSocketService.MAX_OUTBOX) {
      // Drop the oldest to make room, and surface a toast-equivalent so the
      // user has a chance to notice the queue is overwhelmed.
      this.outbox.shift();
      this.notify({
        type: 'error',
        code: 'SEND_FAILED',
        detail: 'Send queue full; oldest message dropped',
      });
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

export const chatSocket = new ChatSocketService();
