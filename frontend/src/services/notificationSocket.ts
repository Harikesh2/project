import { NotificationWsEvent } from '@/types';

type EventCallback = (event: NotificationWsEvent) => void;
export type ConnectionState = 'idle' | 'connecting' | 'open' | 'closed';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function getWsUrl(): string {
  const base = API_BASE_URL.replace(/^http/, 'ws') + '/ws/notifications';
  return base;
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

class NotificationSocketService {
  private ws: WebSocket | null = null;
  private listeners: Set<EventCallback> = new Set();
  private connectionListeners: Set<(state: ConnectionState) => void> = new Set();
  private state: ConnectionState = 'idle';
  private shouldReconnect = false;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private setState(next: ConnectionState): void {
    if (this.state === next) return;
    this.state = next;
    for (const cb of this.connectionListeners) cb(next);
  }

  private get backoffDelay(): number {
    return Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000) + Math.random() * 1000;
  }

  subscribe(cb: EventCallback): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  subscribeConnection(cb: (state: ConnectionState) => void): () => void {
    this.connectionListeners.add(cb);
    cb(this.state);
    return () => this.connectionListeners.delete(cb);
  }

  private notify(event: NotificationWsEvent): void {
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

    const url = `${getWsUrl()}?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(url);
    this.setState('connecting');

    this.ws.onopen = () => {
      this.setState('open');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as NotificationWsEvent;
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
}

export const notificationSocket = new NotificationSocketService();
