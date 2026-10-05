"use client";

import { Hourglass } from "lucide-react";
import { useState } from "react";

import { PanelEmpty, PanelError, PanelLoading, StaleBadge } from "@/components/layout/states";
import { TimeText } from "@/components/tss/time-text";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useNow } from "@/hooks/use-now";
import { useSignals, useStatus } from "@/hooks/use-queries";
import type { SignalSymbol } from "@/types/api";

import { SignalCard } from "./signal-card";

function SymbolList({ items, now, empty }: { items: SignalSymbol[]; now: number; empty: React.ReactNode }) {
  if (items.length === 0) return <>{empty}</>;
  return (
    <>
      {items.map((item) => (
        <SignalCard key={item.symbol} item={item} now={now} />
      ))}
    </>
  );
}

export function SignalsPanel() {
  const [tab, setTab] = useState<string>("momentum");
  const signals = useSignals();
  const status = useStatus();
  const now = useNow(30_000);
  const data = signals.data;
  const stale = signals.isError && data !== undefined;
  const run = status.data?.runs.find((r) => r.agent === "signal");
  const skipped = Object.keys((run?.meta?.skipped ?? {}) as Record<string, string>).length;
  const momentum = (data?.symbols ?? []).filter((s) => s.group === "momentum");
  const majors = (data?.symbols ?? []).filter((s) => s.group === "majors");
  const nextRun = status.data?.next_runs.signal ?? null;

  return (
    <section
      aria-label="Signals"
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card"
    >
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))} className="min-h-0 flex-1 gap-0">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-2">
          <h2 className="text-sm font-semibold">Signals</h2>
          <TabsList variant="line" aria-label="Signal groups">
            <TabsTrigger value="momentum">Momentum ({momentum.length})</TabsTrigger>
            <TabsTrigger value="majors">Majors ({majors.length})</TabsTrigger>
          </TabsList>
          {stale ? <StaleBadge reason="The latest refresh failed; showing the last data" /> : null}
          <span className="text-xs text-muted-foreground">FGI Replica V3 · closed bars only</span>
          {data?.updated_at ? (
            <span className="ml-auto text-[11px] text-muted-foreground">
              updated <TimeText iso={data.updated_at} />
            </span>
          ) : null}
        </header>

        <div className="min-h-0 flex-1 overflow-auto">
          {signals.isLoading ? (
            <PanelLoading rows={5} />
          ) : signals.isError && !data ? (
            <PanelError error={signals.error} />
          ) : (
            <>
              {skipped > 0 ? (
                <p className="flex items-center gap-2 border-b border-border bg-warn-bg px-3 py-1.5 text-xs text-warn">
                  <Hourglass aria-hidden className="size-3.5" />
                  {skipped} symbol/timeframe combination{skipped === 1 ? "" : "s"} skipped: not enough or
                  outdated history (see the Signals chip).
                </p>
              ) : null}
              <TabsContent value="momentum">
                <SymbolList
                  items={momentum}
                  now={now}
                  empty={
                    <PanelEmpty
                      title="No momentum symbols with signals yet"
                      hint={
                        <>
                          Signals appear for symbols that pass the momentum gate and have enough history. BTC, ETH,
                          SOL and XRP are on the Majors tab. Next run <TimeText iso={nextRun} />.
                        </>
                      }
                    />
                  }
                />
              </TabsContent>
              <TabsContent value="majors">
                <SymbolList
                  items={majors}
                  now={now}
                  empty={
                    <PanelEmpty
                      title="No signals for the majors yet"
                      hint={
                        <>
                          Each timeframe needs 500 closed bars of history. Next run <TimeText iso={nextRun} />.
                        </>
                      }
                    />
                  }
                />
              </TabsContent>
            </>
          )}
        </div>
      </Tabs>
    </section>
  );
}
