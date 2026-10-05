import type { TssEvent } from "@/types/events";

export type WsStatus = "connecting" | "open" | "closed";

const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000, 30000];

type EventListener = (event: TssEvent) => void;

/** One WebSocket per browser tab (shared through context). Reconnects with backoff. */
export class WsClient {
  private socket: WebSocket | null = null;
  private status: WsStatus = "connecting";
  private attempt = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private everOpened = false;
  private stopped = true;
  private readonly eventListeners = new Set<EventListener>();
  private readonly statusListeners = new Set<() => void>();
  private readonly resyncListeners = new Set<() => void>();

  constructor(private readonly url: string) {}

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.socket?.close();
    this.socket = null;
    this.setStatus("closed");
  }

  getStatus = (): WsStatus => this.status;

  onStatus = (listener: () => void): (() => void) => {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  };

  onEvent(listener: EventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  /** Fired on every reconnect (not the first connect): refetch everything once. */
  onResync(listener: () => void): () => void {
    this.resyncListeners.add(listener);
    return () => this.resyncListeners.delete(listener);
  }

  private setStatus(status: WsStatus): void {
    if (this.status === status) return;
    this.status = status;
    this.statusListeners.forEach((l) => l());
  }

  private connect(): void {
    if (this.stopped) return;
    this.setStatus("connecting");
    const socket = new WebSocket(this.url);
    this.socket = socket;
    socket.onopen = () => {
      this.attempt = 0;
      this.setStatus("open");
      if (this.everOpened) this.resyncListeners.forEach((l) => l());
      this.everOpened = true;
    };
    socket.onmessage = (message: MessageEvent<string>) => {
      let event: TssEvent;
      try {
        event = JSON.parse(message.data) as TssEvent;
      } catch {
        return;
      }
      if (event && typeof event.type === "string") this.eventListeners.forEach((l) => l(event));
    };
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.setStatus("closed");
      this.scheduleReconnect();
    };
    socket.onerror = () => socket.close();
  }

  private scheduleReconnect(): void {
    if (this.stopped) return;
    const base = BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)];
    this.attempt += 1;
    this.timer = setTimeout(() => this.connect(), base + Math.random() * 500);
  }
}

export function defaultWsUrl(): string {
  const override = process.env.NEXT_PUBLIC_WS_URL;
  if (override) return override;
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}/ws`;
}
