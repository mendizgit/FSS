import type { TickerEvent } from "@/types/events";

export interface LiveTick {
  price: number;
  previous: number | null;
  at: number;
}

// Live prices live outside React Query: ticks never trigger refetches (integration skill).
const ticks = new Map<string, LiveTick>();
const listeners = new Map<string, Set<() => void>>();

export function applyTick(event: TickerEvent): void {
  const { symbol, last_price: price } = event.data;
  if (price === null || !Number.isFinite(price)) return;
  const prev = ticks.get(symbol);
  if (prev && prev.price === price) return;
  ticks.set(symbol, { price, previous: prev?.price ?? null, at: Date.now() });
  listeners.get(symbol)?.forEach((l) => l());
  noteTick();
}

export function subscribeTick(symbol: string, listener: () => void): () => void {
  let set = listeners.get(symbol);
  if (!set) {
    set = new Set();
    listeners.set(symbol, set);
  }
  set.add(listener);
  return () => {
    set.delete(listener);
  };
}

export function getTick(symbol: string): LiveTick | undefined {
  return ticks.get(symbol);
}

// Any tick at all (for the "last price tick" freshness cue in the status bar).
let lastTickAt = 0;
const anyListeners = new Set<() => void>();

export function noteTick(): void {
  lastTickAt = Date.now();
  anyListeners.forEach((l) => l());
}

export function subscribeAnyTick(listener: () => void): () => void {
  anyListeners.add(listener);
  return () => {
    anyListeners.delete(listener);
  };
}

export function getLastTickAt(): number {
  return lastTickAt;
}
