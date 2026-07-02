/** WsClient: reconnect backoff, message parsing, garbage tolerance (P4 tests). */
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { WsClient } from "./client";
import type { ServerMessage } from "../types/generated/ws";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  closed = false;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
  close() {
    this.closed = true;
    this.onclose?.();
  }
  // test helpers
  serverOpen() { this.onopen?.(); }
  serverSend(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) }); }
  serverSendRaw(data: string) { this.onmessage?.({ data }); }
  serverDrop() { this.onclose?.(); }
}

let messages: ServerMessage[];
let connections: boolean[];

function makeClient(opts: Partial<ConstructorParameters<typeof WsClient>[0]> = {}) {
  return new WsClient({
    url: "ws://test/ws",
    onMessage: (m) => messages.push(m),
    onConnected: (c) => connections.push(c),
    wsFactory: (u) => new FakeWebSocket(u) as unknown as WebSocket,
    minBackoffMs: 100,
    maxBackoffMs: 800,
    ...opts,
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeWebSocket.instances = [];
  messages = [];
  connections = [];
});

afterEach(() => {
  vi.useRealTimers();
});

test("delivers parsed messages, ignores garbage frames", () => {
  const c = makeClient();
  c.start();
  const ws = FakeWebSocket.instances[0];
  ws.serverOpen();
  ws.serverSend({ type: "atc_activity", ts: 1, channelMhz: 118.1, active: true });
  ws.serverSendRaw("{not json");
  ws.serverSendRaw('"just a string"');
  ws.serverSend({ type: "atc_activity", ts: 2, channelMhz: 118.1, active: false });
  expect(messages).toHaveLength(2);
  expect(connections).toEqual([true]);
  c.stop();
});

test("reconnects with exponential backoff and resets after success", () => {
  const c = makeClient();
  c.start();
  expect(FakeWebSocket.instances).toHaveLength(1);

  FakeWebSocket.instances[0].serverDrop();          // immediate drop
  vi.advanceTimersByTime(100);                       // backoff #1: 100 ms
  expect(FakeWebSocket.instances).toHaveLength(2);

  FakeWebSocket.instances[1].serverDrop();
  vi.advanceTimersByTime(199);                       // backoff #2: 200 ms — not yet
  expect(FakeWebSocket.instances).toHaveLength(2);
  vi.advanceTimersByTime(1);
  expect(FakeWebSocket.instances).toHaveLength(3);

  FakeWebSocket.instances[2].serverOpen();           // success resets backoff
  FakeWebSocket.instances[2].serverDrop();
  vi.advanceTimersByTime(100);                       // back to min backoff
  expect(FakeWebSocket.instances).toHaveLength(4);

  expect(connections).toEqual([false, false, true, false]);
  c.stop();
});

test("backoff caps at maxBackoffMs", () => {
  const c = makeClient();
  c.start();
  // 100 → 200 → 400 → 800 → 800 (capped)
  for (const wait of [100, 200, 400, 800, 800]) {
    FakeWebSocket.instances.at(-1)!.serverDrop();
    vi.advanceTimersByTime(wait - 1);
    const before = FakeWebSocket.instances.length;
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances.length).toBe(before + 1);
  }
  c.stop();
});

test("stop() prevents further reconnects", () => {
  const c = makeClient();
  c.start();
  c.stop();
  vi.advanceTimersByTime(5000);
  expect(FakeWebSocket.instances).toHaveLength(1);
});
