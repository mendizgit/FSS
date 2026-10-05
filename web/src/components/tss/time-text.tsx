"use client";

import { Tip } from "@/components/tss/tip";
import { formatIstDateTime, formatIstTime, formatUtc } from "@/lib/time";

/** IST text with the UTC instant in the tooltip. */
export function TimeText({
  iso,
  withDate = false,
  className,
}: {
  iso: string | null | undefined;
  withDate?: boolean;
  className?: string;
}) {
  return (
    <Tip content={formatUtc(iso)} focusable>
      <time dateTime={iso ?? undefined} className={className ?? "num"}>
        {withDate ? formatIstDateTime(iso) : formatIstTime(iso)}
      </time>
    </Tip>
  );
}
