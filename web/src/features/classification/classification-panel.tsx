"use client";

import { Hourglass } from "lucide-react";
import { useMemo, useState } from "react";

import { PanelEmpty, PanelError, PanelLoading, StaleBadge } from "@/components/layout/states";
import { TimeText } from "@/components/tss/time-text";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useClassification, useDiscovery, useStatus } from "@/hooks/use-queries";
import type { WindowId } from "@/types/api";

import { buildViewRows, ClassificationTable } from "./classification-table";
import { DetailDrawer } from "./detail-drawer";
import { PoolTable } from "./pool-table";
import { WindowToggle } from "./window-toggle";

export function ClassificationPanel() {
  const [window, setWindow] = useState<WindowId>("1h");
  const [tab, setTab] = useState<string>("classification");
  const [selected, setSelected] = useState<string | null>(null);

  const classification = useClassification(window);
  const discovery = useDiscovery();
  const status = useStatus();

  const discoveryRows = useMemo(
    () => [...(discovery.data?.pool ?? []), ...(discovery.data?.pinned ?? [])],
    [discovery.data],
  );
  const rows = useMemo(
    () => buildViewRows(classification.data?.rows ?? [], discoveryRows),
    [classification.data, discoveryRows],
  );
  const selectedRow = rows.find((r) => r.symbol === selected) ?? null;
  const nextPipeline = status.data?.next_runs.pipeline ?? null;
  const warming = status.data?.state === "WARMING_UP";
  const stale = (classification.isError && classification.data !== undefined) ||
    (discovery.isError && discovery.data !== undefined);

  return (
    <section
      aria-label="Classification"
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card"
    >
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))} className="min-h-0 flex-1 gap-0">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-2">
          <h2 className="text-sm font-semibold">Derivatives</h2>
          <TabsList variant="line" aria-label="Derivatives views">
            <TabsTrigger value="classification">Classification</TabsTrigger>
            <TabsTrigger value="pool">Movers pool ({discovery.data?.pool.length ?? 50})</TabsTrigger>
          </TabsList>
          {stale ? <StaleBadge reason="Showing the last data received; the latest refresh failed" /> : null}
          <div className="ml-auto flex items-center gap-3">
            {classification.data?.ts && tab === "classification" ? (
              <span className="text-[11px] text-muted-foreground">
                updated <TimeText iso={classification.data.ts} />
              </span>
            ) : null}
            {tab === "classification" ? <WindowToggle value={window} onChange={setWindow} /> : null}
          </div>
        </header>

        <TabsContent value="classification" className="min-h-0 flex-1 overflow-auto">
          {classification.isLoading || discovery.isLoading ? (
            <PanelLoading rows={8} />
          ) : classification.isError && !classification.data ? (
            <PanelError error={classification.error} />
          ) : rows.length === 0 ? (
            <PanelEmpty
              title="No classification yet"
              hint={
                <>
                  The first 15-minute cycle has not completed. Next run{" "}
                  <TimeText iso={nextPipeline} />.
                </>
              }
            />
          ) : (
            <>
              {warming ? (
                <p className="flex items-center gap-2 border-b border-border bg-warn-bg px-3 py-1.5 text-xs text-warn">
                  <Hourglass aria-hidden className="size-3.5" />
                  Warming up: open-interest history is shorter than the window, so states stay
                  “Unreliable” until 1 h / 4 h of snapshots exist.
                </p>
              ) : null}
              <ClassificationTable
                rows={rows}
                window={window}
                onSelect={setSelected}
                emptyNote={
                  <>
                    No symbols passed the momentum gate this cycle. Next update{" "}
                    <TimeText iso={nextPipeline} />.
                  </>
                }
              />
              <p className="border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
                Liquidations are not shown: MEXC does not publish a public liquidation feed.
              </p>
            </>
          )}
        </TabsContent>

        <TabsContent value="pool" className="min-h-0 flex-1 overflow-auto">
          {discovery.isLoading ? (
            <PanelLoading rows={8} />
          ) : discovery.isError && !discovery.data ? (
            <PanelError error={discovery.error} />
          ) : (discovery.data?.pool.length ?? 0) === 0 ? (
            <PanelEmpty title="The movers pool is empty" hint="It fills after the first 15-minute cycle." />
          ) : (
            <PoolTable rows={discovery.data?.pool ?? []} />
          )}
        </TabsContent>
      </Tabs>
      <DetailDrawer row={selectedRow} window={window} onClose={() => setSelected(null)} />
    </section>
  );
}
