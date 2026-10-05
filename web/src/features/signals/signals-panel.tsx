"use client";

import { Hourglass } from "lucide-react";

import { Panel } from "@/components/layout/panel";
import { PanelEmpty, PanelError, PanelLoading, StaleBadge } from "@/components/layout/states";
import { TimeText } from "@/components/tss/time-text";
import { useNow } from "@/hooks/use-now";
import { useSignals, useStatus } from "@/hooks/use-queries";

import { SignalCard } from "./signal-card";

export function SignalsPanel() {
  const signals = useSignals();
  const status = useStatus();
  const now = useNow(30_000);
  const data = signals.data;
  const stale = signals.isError && data !== undefined;
  const run = status.data?.runs.find((r) => r.agent === "signal");
  const skipped = Object.keys((run?.meta?.skipped ?? {}) as Record<string, string>).length;

  return (
    <Panel
      title="Signals"
      subtitle="FGI Replica V3 · closed bars only"
      badge={stale ? <StaleBadge reason="The latest refresh failed; showing the last data" /> : null}
      actions={
        data?.updated_at ? (
          <span className="text-[11px] text-muted-foreground">
            updated <TimeText iso={data.updated_at} />
          </span>
        ) : null
      }
      className="min-h-0 flex-1"
    >
      {signals.isLoading ? (
        <PanelLoading rows={5} />
      ) : signals.isError && !data ? (
        <PanelError error={signals.error} />
      ) : !data || data.symbols.length === 0 ? (
        <PanelEmpty
          title="No signals yet"
          hint={
            <>
              The signal engine runs every 5 minutes on closed 5m / 15m / 1h bars and needs 500 bars per
              timeframe. Next run <TimeText iso={status.data?.next_runs.signal ?? null} />.
            </>
          }
        />
      ) : (
        <>
          {skipped > 0 ? (
            <p className="flex items-center gap-2 border-b border-border bg-warn-bg px-3 py-1.5 text-xs text-warn">
              <Hourglass aria-hidden className="size-3.5" />
              {skipped} symbol/timeframe combination{skipped === 1 ? "" : "s"} skipped: not enough or
              outdated history (see the Signals chip).
            </p>
          ) : null}
          {data.symbols.map((item) => (
            <SignalCard key={item.symbol} item={item} now={now} />
          ))}
        </>
      )}
    </Panel>
  );
}
