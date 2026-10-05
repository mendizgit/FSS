"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { getLastTickAt, subscribeAnyTick } from "@/lib/price-store";

/** Seconds since the newest price tick (null before the first one). Re-renders every second. */
export function useTickAgeSeconds(): number | null {
  const last = useSyncExternalStore(subscribeAnyTick, getLastTickAt, () => 0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return last === 0 ? null : Math.max(0, Math.round((now - last) / 1000));
}
