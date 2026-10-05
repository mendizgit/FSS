"use client";

import { Change } from "@/components/tss/change";
import { LivePrice } from "@/components/tss/live-price";
import { SymbolLabel } from "@/components/tss/symbol-label";
import { useSort } from "@/hooks/use-sort";
import { formatFunding, formatFundingDelta, formatUsdCompact } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ClassificationRow, DiscoveryRow, WindowId } from "@/types/api";

import { FlagChips } from "./flag-chips";
import { PlainHead, SortHead } from "./sort-head";
import { StateBadge } from "./state-badge";

export interface ClassificationViewRow extends ClassificationRow {
  selectionRank: number | null;
  zeroFee: boolean | null;
}

type SortKey = "rank" | "symbol" | "change15m" | "change" | "oiChange" | "volChange" | "spotChange" | "funding";

const ACCESSORS: Record<SortKey, (r: ClassificationViewRow) => number | string | null> = {
  rank: (r) => r.selectionRank,
  symbol: (r) => r.symbol,
  change15m: (r) => r.price_change_15m_pct,
  change: (r) => r.price_change_pct,
  oiChange: (r) => r.oi_change_pct,
  volChange: (r) => r.fut_volume_change_pct,
  spotChange: (r) => r.spot_volume_change_pct,
  funding: (r) => r.funding_now,
};

export function buildViewRows(
  rows: ClassificationRow[],
  discovery: DiscoveryRow[],
): ClassificationViewRow[] {
  const bySymbol = new Map(discovery.map((d) => [d.symbol, d]));
  return rows.map((r) => ({
    ...r,
    selectionRank: bySymbol.get(r.symbol)?.selection_rank ?? null,
    zeroFee: bySymbol.get(r.symbol)?.zero_fee ?? null,
  }));
}

function isStale(row: ClassificationRow): boolean {
  return row.unreliable_reasons.includes("snapshot_stale");
}

function Cells({
  row,
  onSelect,
}: {
  row: ClassificationViewRow;
  onSelect: (symbol: string) => void;
}) {
  const stale = isStale(row);
  return (
    <tr className={cn("group h-10 border-b border-border/60 hover:bg-muted/50", stale && "opacity-60")}>
      <td className="sticky left-0 z-[1] bg-card px-2 text-left group-hover:bg-muted">
        <button
          type="button"
          onClick={() => onSelect(row.symbol)}
          aria-label={`Details for ${row.symbol}`}
          className="rounded text-left hover:underline"
        >
          <SymbolLabel symbol={row.symbol} zeroFee={row.zeroFee} hideQuote />
        </button>
        {stale ? <div className="text-[10px] text-warn">stale: snapshot older than 10 min</div> : null}
      </td>
      <td className="px-1.5 text-left">
        <StateBadge state={row.state} reasons={row.unreliable_reasons} />
      </td>
      <td className="px-1.5 text-right">
        <LivePrice symbol={row.symbol} fallback={row.last_price} />
      </td>
      <td className="px-1.5 text-right">
        <Change value={row.price_change_15m_pct} />
      </td>
      <td className="px-1.5 text-right">
        <Change value={row.price_change_pct} />
      </td>
      <td className="px-1.5 text-right leading-tight">
        <div className="num">{formatUsdCompact(row.oi_notional_usdt)}</div>
        <Change value={row.oi_change_pct} className="text-[11px]" />
      </td>
      <td className="px-1.5 text-right">
        <Change value={row.fut_volume_change_pct} digits={1} />
      </td>
      <td className="px-1.5 text-right">
        {row.spot_volume_change_pct === null ? (
          <span className="text-muted-foreground" title="No spot market or no spot data">
            —
          </span>
        ) : (
          <Change value={row.spot_volume_change_pct} digits={1} />
        )}
      </td>
      <td className="px-1.5 text-right leading-tight">
        <div className="num">{formatFunding(row.funding_now)}</div>
        <div className="num text-[11px] text-muted-foreground">Δ {formatFundingDelta(row.funding_delta)}</div>
      </td>
      <td className="px-1.5 text-left">
        <FlagChips flags={row.flags} />
      </td>
    </tr>
  );
}

export function ClassificationTable({
  rows,
  window,
  onSelect,
  emptyNote,
}: {
  rows: ClassificationViewRow[];
  window: WindowId;
  onSelect: (symbol: string) => void;
  emptyNote: React.ReactNode;
}) {
  const pinned = rows.filter((r) => r.pinned).sort((a, b) => a.symbol.localeCompare(b.symbol));
  const selected = rows.filter((r) => !r.pinned);
  const { sorted, sort, toggle } = useSort<ClassificationViewRow, SortKey>(selected, ACCESSORS, { key: "rank", dir: "asc" });
  const w = window;
  return (
    <table className="w-full min-w-[860px] border-collapse text-[12px]">
      <thead>
        <tr>
          <SortHead label="Symbol" sortKey="symbol" sort={sort} onSort={toggle} align="left" sticky />
          <PlainHead align="left">State</PlainHead>
          <PlainHead>Price</PlainHead>
          <SortHead label="15m" sortKey="change15m" sort={sort} onSort={toggle} title="Last closed 15m bar" />
          <SortHead label={w} sortKey="change" sort={sort} onSort={toggle} title={`Price change over ${w}`} />
          <SortHead label={`OI · Δ${w}`} sortKey="oiChange" sort={sort} onSort={toggle} title="Open-interest notional, and its change over the window (contracts)" />
          <SortHead label={`Fut vol Δ${w}`} sortKey="volChange" sort={sort} onSort={toggle} title="Futures turnover, this window vs the previous one" />
          <SortHead label={`Spot vol Δ${w}`} sortKey="spotChange" sort={sort} onSort={toggle} title="Spot turnover, this window vs the previous one" />
          <SortHead label="Funding · Δ" sortKey="funding" sort={sort} onSort={toggle} title="Current funding rate and its change over the window" />
          <PlainHead align="left">Flags</PlainHead>
        </tr>
      </thead>
      <tbody>
        {pinned.length > 0 ? (
          <>
            <tr>
              <th
                colSpan={10}
                scope="colgroup"
                className="bg-secondary/60 px-2 py-1 text-left text-[10px] font-semibold tracking-wide text-muted-foreground uppercase"
              >
                Market context
              </th>
            </tr>
            {pinned.map((r) => (
              <Cells key={`${r.symbol}-p`} row={r} onSelect={onSelect} />
            ))}
          </>
        ) : null}
        <tr>
          <th
            colSpan={10}
            scope="colgroup"
            className="bg-secondary/60 px-2 py-1 text-left text-[10px] font-semibold tracking-wide text-muted-foreground uppercase"
          >
            Selected by momentum ({selected.length})
          </th>
        </tr>
        {sorted.map((r) => (
          <Cells key={r.symbol} row={r} onSelect={onSelect} />
        ))}
        {selected.length === 0 ? (
          <tr>
            <td colSpan={10} className="px-3 py-6 text-center text-xs text-muted-foreground">
              {emptyNote}
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}
