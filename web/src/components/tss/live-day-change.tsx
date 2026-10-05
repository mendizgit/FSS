"use client";

import { Change } from "@/components/tss/change";
import { useLiveTick } from "@/hooks/use-live-price";
import { pctChange } from "@/lib/format";

/** Change since 00:00 UTC, recomputed from the live price and the day's open. Falls back to the
 * server value (from the last snapshot) until a tick arrives or when the open is unknown. */
export function LiveDayChange({
  symbol,
  dayOpen,
  fallback,
}: {
  symbol: string;
  dayOpen: number | null;
  fallback: number | null;
}) {
  const tick = useLiveTick(symbol);
  const live = tick && dayOpen ? pctChange(tick.price, dayOpen) : null;
  return <Change value={live ?? fallback} />;
}
