import { Tip } from "@/components/tss/tip";

import { FLAG_META } from "./meta";

/** Informational flags as small chips. LIQUIDATIONS_UNAVAILABLE is always set, so it is
 * explained in the panel footnote instead of repeated on every row. */
export function FlagChips({
  flags,
  includeAlways = false,
}: {
  flags: string[];
  includeAlways?: boolean;
}) {
  const visible = flags.filter((f) => includeAlways || f !== "LIQUIDATIONS_UNAVAILABLE");
  if (visible.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {visible.map((flag) => {
        const meta = FLAG_META[flag];
        return (
          <Tip key={flag} content={meta?.meaning ?? flag} focusable>
            <span className="num rounded border border-border bg-secondary px-1 text-[10px] leading-4 text-secondary-foreground">
              {meta?.abbr ?? flag}
            </span>
          </Tip>
        );
      })}
    </span>
  );
}
