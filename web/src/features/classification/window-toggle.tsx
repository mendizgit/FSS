"use client";

import { cn } from "@/lib/utils";
import type { WindowId } from "@/types/api";

const OPTIONS: WindowId[] = ["1h", "4h"];

/** Segmented 1h / 4h control (a labelled group of toggle buttons). */
export function WindowToggle({
  value,
  onChange,
}: {
  value: WindowId;
  onChange: (value: WindowId) => void;
}) {
  return (
    <div role="group" aria-label="Classification window" className="inline-flex rounded-md border border-border p-0.5">
      {OPTIONS.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          onClick={() => onChange(option)}
          className={cn(
            "num h-6 rounded px-2.5 text-xs font-medium transition-colors",
            value === option
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
