"use client";

import { useSyncExternalStore } from "react";

import { getTick, type LiveTick, subscribeTick } from "@/lib/price-store";

export function useLiveTick(symbol: string): LiveTick | undefined {
  return useSyncExternalStore(
    (listener) => subscribeTick(symbol, listener),
    () => getTick(symbol),
    () => undefined,
  );
}
