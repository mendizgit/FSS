"use client";

import { Panel } from "@/components/layout/panel";
import { PanelEmpty, PanelError, PanelLoading, PanelWarming, StaleBadge } from "@/components/layout/states";
import { Change } from "@/components/tss/change";
import { LivePrice } from "@/components/tss/live-price";
import { SymbolLabel } from "@/components/tss/symbol-label";
import { TimeText } from "@/components/tss/time-text";
import { useMovers } from "@/hooks/use-queries";
import { formatUsdCompact } from "@/lib/format";
import type { MoverRow } from "@/types/api";

function MoverList({ title, rows, tone }: { title: string; rows: MoverRow[]; tone: "up" | "down" }) {
  return (
    <div className="min-w-0">
      <h3 className={`px-2 pb-1 text-xs font-semibold ${tone === "up" ? "text-up" : "text-down"}`}>
        <span aria-hidden>{tone === "up" ? "▲ " : "▼ "}</span>
        {title}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[300px] border-collapse text-[12px]">
          <caption className="sr-only">{title} since 00:00 UTC</caption>
          <thead>
            <tr className="text-[11px] text-muted-foreground">
              <th scope="col" className="h-7 whitespace-nowrap px-1 text-left font-medium">#</th>
              <th scope="col" className="h-7 whitespace-nowrap px-1 text-left font-medium">Symbol</th>
              <th scope="col" className="h-7 whitespace-nowrap px-1 text-right font-medium">UTC day</th>
              <th scope="col" className="h-7 whitespace-nowrap px-1 text-right font-medium">Price</th>
              <th scope="col" className="h-7 whitespace-nowrap px-1 text-right font-medium">24h turnover</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol} className="h-9 border-t border-border/60 hover:bg-muted/50">
                <td className="num px-1 text-left text-muted-foreground">{r.rank}</td>
                <td className="px-1 text-left">
                  <SymbolLabel symbol={r.symbol} hideQuote />
                </td>
                <td className="px-1 text-right">
                  <Change value={r.change_pct} />
                </td>
                <td className="px-1 text-right">
                  <LivePrice symbol={r.symbol} fallback={r.last_price} />
                </td>
                <td className="num px-1 text-right">{formatUsdCompact(r.fut_amount24)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function MoversPanel() {
  const movers = useMovers();
  const data = movers.data;
  const stale = movers.isError && data !== undefined;
  return (
    <Panel
      title="Market Movers"
      subtitle="Since 00:00 UTC (05:30 IST)"
      badge={stale ? <StaleBadge reason="The latest refresh failed; showing the last data" /> : null}
      actions={
        data?.ts ? (
          <span className="text-[11px] text-muted-foreground">
            updated <TimeText iso={data.ts} />
          </span>
        ) : null
      }
      className="min-h-0 flex-1"
    >
      {movers.isLoading ? (
        <PanelLoading rows={6} />
      ) : movers.isError && !data ? (
        <PanelError error={movers.error} />
      ) : data?.status === "WAITING_DAY_OPEN" ? (
        <PanelWarming
          title="Waiting for today’s opens"
          hint="The UTC day just rolled over (00:00 UTC = 05:30 IST). Movers appear within a minute."
        />
      ) : !data || data.status === "NO_DATA" || (data.gainers.length === 0 && data.losers.length === 0) ? (
        <PanelEmpty
          title="No movers yet"
          hint="They appear after the first snapshot and the first kline sync."
        />
      ) : (
        <div className="@container p-2">
          <div className="grid gap-4 @xl:grid-cols-2">
          <MoverList title="Top 10 Gainers" rows={data.gainers} tone="up" />
          <MoverList title="Top 10 Losers" rows={data.losers} tone="down" />
          </div>
        </div>
      )}
    </Panel>
  );
}
