"use client";

import { useEffect, useRef, useState } from "react";

import { useLiveTick } from "@/hooks/use-live-price";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Price cell: shows the live tick when available, otherwise the snapshot price. Flashes <= 600 ms. */
export function LivePrice({
  symbol,
  fallback,
  className,
}: {
  symbol: string;
  fallback: number | null;
  className?: string;
}) {
  const tick = useLiveTick(symbol);
  const price = tick?.price ?? fallback;
  const shown = useRef<number | null>(price);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    const before = shown.current;
    shown.current = price;
    if (before === null || price === null || before === price) return;
    setFlash(price > before ? "up" : "down");
    const id = setTimeout(() => setFlash(null), 600);
    return () => clearTimeout(id);
  }, [price]);

  return (
    <span
      className={cn(
        "num rounded-sm px-1",
        flash === "up" && "flash-up",
        flash === "down" && "flash-down",
        className,
      )}
    >
      {formatPrice(price)}
    </span>
  );
}
