"use client";

import { Check, X } from "lucide-react";

import { Change } from "@/components/tss/change";
import { LivePrice } from "@/components/tss/live-price";
import { SymbolLabel } from "@/components/tss/symbol-label";
import { useSort } from "@/hooks/use-sort";
import { formatFunding, formatRvol, formatUsdCompact } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DiscoveryRow } from "@/types/api";

import { PlainHead, SortHead } from "./sort-head";

type SortKey = "rank" | "symbol" | "change15m" | "rvol" | "dayChange" | "turnover" | "selection";

const ACCESSORS: Record<SortKey, (r: DiscoveryRow) => number | string | null> = {
  rank: (r) => r.pool_rank,
  symbol: (r) => r.symbol,
  change15m: (r) => r.price_change_15m_pct,
  rvol: (r) => r.rvol_15m,
  dayChange: (r) => r.utc_day_change_pct,
  turnover: (r) => r.fut_amount24,
  selection: (r) => r.selection_rank,
};

export function PoolTable({ rows }: { rows: DiscoveryRow[] }) {
  const { sorted, sort, toggle } = useSort<DiscoveryRow, SortKey>(rows, ACCESSORS, { key: "rank", dir: "asc" });
  return (
    <table className="w-full min-w-[900px] border-collapse text-[12px]">
      <thead>
        <tr>
          <SortHead label="#" sortKey="rank" sort={sort} onSort={toggle} align="left" title="Pool rank by RVOL" />
          <SortHead label="Symbol" sortKey="symbol" sort={sort} onSort={toggle} align="left" />
          <PlainHead>Price</PlainHead>
          <SortHead label="15m" sortKey="change15m" sort={sort} onSort={toggle} />
          <SortHead label="RVOL" sortKey="rvol" sort={sort} onSort={toggle} title="Last 15m turnover / median of the previous 96 bars" />
          <PlainHead align="left">Gate 2</PlainHead>
          <SortHead label="Sel #" sortKey="selection" sort={sort} onSort={toggle} title="Rank among the selected (max 20)" />
          <SortHead label="UTC day" sortKey="dayChange" sort={sort} onSort={toggle} title="Change since 00:00 UTC" />
          <SortHead label="24h turnover" sortKey="turnover" sort={sort} onSort={toggle} />
          <PlainHead>OI</PlainHead>
          <PlainHead>Funding</PlainHead>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.symbol} className="h-9 border-b border-border/60 hover:bg-muted/50">
            <td className="num px-2 text-left text-muted-foreground">{r.pool_rank ?? "—"}</td>
            <td className="px-2 text-left">
              <SymbolLabel symbol={r.symbol} zeroFee={r.zero_fee} context={r.pinned} />
            </td>
            <td className="px-2 text-right">
              <LivePrice symbol={r.symbol} fallback={r.last_price} />
            </td>
            <td className="px-2 text-right">
              <Change value={r.price_change_15m_pct} />
            </td>
            <td className="num px-2 text-right">{formatRvol(r.rvol_15m)}</td>
            <td className="px-2 text-left">
              <span
                className={cn(
                  "inline-flex items-center gap-1 text-[11px] font-medium",
                  r.passed_gate2 ? "text-up" : "text-muted-foreground",
                )}
              >
                {r.passed_gate2 ? <Check aria-hidden className="size-3" /> : <X aria-hidden className="size-3" />}
                {r.passed_gate2 ? "pass" : "fail"}
              </span>
            </td>
            <td className="num px-2 text-right">{r.selection_rank ?? "—"}</td>
            <td className="px-2 text-right">
              <Change value={r.utc_day_change_pct} />
            </td>
            <td className="num px-2 text-right">{formatUsdCompact(r.fut_amount24)}</td>
            <td className="num px-2 text-right">{formatUsdCompact(r.oi_notional_usdt)}</td>
            <td className="num px-2 text-right">{formatFunding(r.funding_rate)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
