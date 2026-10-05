import { Tip } from "@/components/tss/tip";
import { cn } from "@/lib/utils";

import { reasonText, STATE_META } from "./meta";

const TONE_SOLID = {
  up: "border-transparent bg-up text-background",
  down: "border-transparent bg-down text-background",
  muted: "border-transparent bg-muted text-muted-foreground",
  warn: "border-warn/60 bg-warn-bg text-warn",
} as const;

const TONE_OUTLINE = {
  up: "border-up text-up bg-transparent",
  down: "border-down text-down bg-transparent",
  muted: "border-border text-muted-foreground bg-transparent",
  warn: "border-warn text-warn bg-transparent",
} as const;

/** State badge: icon + text, never colour alone. */
export function StateBadge({
  state,
  reasons,
  tooltip = true,
}: {
  state: string;
  reasons?: string[];
  tooltip?: boolean;
}) {
  const meta = STATE_META[state] ?? STATE_META.NEUTRAL;
  const Icon = meta.icon;
  const tip = (
    <div className="flex flex-col gap-1">
      <span>{meta.meaning}</span>
      {reasons?.length ? (
        <ul className="list-disc pl-4">
          {reasons.map((r) => (
            <li key={r}>{reasonText(r)}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
  const badge = (
      <span
        className={cn(
          "inline-flex h-5 items-center gap-1 rounded-md border px-1.5 text-[11px] font-medium whitespace-nowrap",
          meta.outlined ? TONE_OUTLINE[meta.tone] : TONE_SOLID[meta.tone],
          state === "UNRELIABLE" && "hatched",
        )}
      >
        <Icon aria-hidden className="size-3" />
        {meta.label}
      </span>
  );
  return tooltip ? (
    <Tip content={tip} focusable>
      {badge}
    </Tip>
  ) : (
    badge
  );
}
