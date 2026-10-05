import { directionOf, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Directional value: icon + sign + colour, never colour alone. */
export function Change({
  value,
  digits = 2,
  className,
}: {
  value: number | null | undefined;
  digits?: number;
  className?: string;
}) {
  const dir = directionOf(value);
  return (
    <span
      className={cn(
        "num inline-flex items-center gap-1 whitespace-nowrap",
        dir === "up" && "text-up",
        dir === "down" && "text-down",
        dir === "flat" && "text-muted-foreground",
        className,
      )}
    >
      <span aria-hidden className="text-[9px] leading-none">
        {dir === "up" ? "▲" : dir === "down" ? "▼" : "•"}
      </span>
      {formatPct(value, digits)}
    </span>
  );
}
