/**
 * WS client: single connection, exponential-backoff reconnect, snapshot-on-
 * connect handled by the server. The store's `applyServer` is the only sink.
 */
import type { ServerMessage } from "../types/generated/ws";

export interface WsClientOptions {
  url?: string;
  onMessage: (msg: ServerMessage) => void;
  onConnected: (connected: boolean) => void;
  /** injection seam for tests */
  wsFactory?: (url: string) => WebSocket;
  minBackoffMs?: number;
  maxBackoffMs?: number;
}

export function defaultWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

export class WsClient {
  private ws: WebSocket | null = null;
  private backoffMs: number;
  private readonly minBackoffMs: number;
  private readonly maxBackoffMs: number;
  private closed = false;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly opts: WsClientOptions) {
    this.minBackoffMs = opts.minBackoffMs ?? 1000;
    this.maxBackoffMs = opts.maxBackoffMs ?? 15000;
    this.backoffMs = this.minBackoffMs;
  }

  start(): void {
    this.closed = false;
    this.connect();
  }

  stop(): void {
    this.closed = true;
    if (this.timer) clearTimeout(this.timer);
    this.ws?.close();
    this.ws = null;
  }

  private connect(): void {
    const url = this.opts.url ?? defaultWsUrl();
    const factory = this.opts.wsFactory ?? ((u: string) => new WebSocket(u));
    const ws = (this.ws = factory(url));

    ws.onopen = () => {
      this.backoffMs = this.minBackoffMs; // healthy again — reset
      this.opts.onConnected(true);
    };

    ws.onmessage = (ev: MessageEvent) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(String(ev.data));
      } catch {
        return; // garbage frame — ignore, never crash the stream
      }
      if (parsed && typeof parsed === "object" && "type" in parsed) {
        this.opts.onMessage(parsed as ServerMessage);
      }
    };

    ws.onclose = () => {
      this.opts.onConnected(false);
      this.ws = null;
      if (this.closed) return;
      this.timer = setTimeout(() => this.connect(), this.backoffMs);
      this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs);
    };

    ws.onerror = () => {
      // onclose always follows onerror; reconnect logic lives there
      ws.close();
    };
  }
}
