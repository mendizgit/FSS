"use client";

import { ArrowDown, ArrowUp, Minus, X } from "lucide-react";

import { LivePrice } from "@/components/tss/live-price";
import { SymbolLabel } from "@/components/tss/symbol-label";
import { Tip } from "@/components/tss/tip";
import { TimeText } from "@/components/tss/time-text";
import { cn } from "@/lib/utils";
import type { SignalRow, SignalSetup, SignalSymbol } from "@/types/api";

import { EVENT_META, isFresh, TF_MINUTES, ZONE_LABEL } from "./meta";

const TONE = { up: "text-up", down: "text-down", muted: "text-muted-foreground" } as const;

function Direction({ value, labelUp, labelDown }: { value: string | null; labelUp: string; labelDown: string }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  const up = value === "UP" || value === "BULL";
  const down = value === "DOWN" || value === "BEAR";
  const Icon = up ? ArrowUp : down ? ArrowDown : Minus;
  return (
    <span className={cn("inline-flex items-center gap-0.5", up ? "text-up" : down ? "text-down" : "text-muted-foreground")}>
      <Icon aria-hidden className="size-3" />
      {up ? labelUp : down ? labelDown : value.toLowerCase()}
    </span>
  );
}

function EventCell({ row }: { row: SignalRow }) {
  const meta = EVENT_META[row.last_event] ?? EVENT_META.NONE;
  if (row.last_event === "NONE") return <span className="text-muted-foreground">none</span>;
  const ago = row.bars_ago === 0 ? "now" : `${row.bars_ago}b ago`;
  return (
    <Tip
      content={
        <div className="flex flex-col gap-1">
          <span>{meta.meaning}</span>
          {row.against_htf ? <span>Against the 4H trend (✗).</span> : null}
          <span>{row.bars_ago === 0 ? "On the newest closed bar." : `${row.bars_ago} bars before the newest closed bar.`}</span>
        </div>
      }
      focusable
    >
      <span className={cn("inline-flex items-center gap-1 whitespace-nowrap", TONE[meta.tone], row.against_htf && "opacity-70")}>
        <span className="font-semibold">{meta.label}</span>
        {row.against_htf ? <X aria-label="against the 4H trend" className="size-3 text-warn" /> : null}
        <span className="num text-[11px] text-muted-foreground">{ago}</span>
        {isFresh(row) ? (
          <span className="rounded bg-accent px-1 text-[10px] font-medium text-accent-foreground">fresh</span>
        ) : null}
      </span>
    </Tip>
  );
}

function Row({ row, now }: { row: SignalRow; now: number }) {
  const ageMin = (now - new Date(row.computed_at).getTime()) / 60000;
  const zone = row.zone_position ? ZONE_LABEL[row.zone_position] : null;
  const stale = ageMin > 3 * Math.max(TF_MINUTES[row.timeframe] ?? 5, 5) + 5;
  return (
    <tr className={cn("h-9 border-t border-border/60", stale && "opacity-60")}>
      <th scope="row" className="num px-2 text-left font-medium">
        <Tip content={<>Bar closed <TimeText iso={row.bar_close_time} /></>} focusable>
          {row.timeframe}
        </Tip>
      </th>
      <td className="px-2"><Direction value={row.m_trend} labelUp="Up" labelDown="Down" /></td>
      <td className="px-2"><EventCell row={row} /></td>
      <td className="px-2">
        {zone ? (
          <Tip content={zone.meaning} focusable>
            <span className={cn("whitespace-nowrap", TONE[zone.tone])}>{zone.text}</span>
          </Tip>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-2">
        {row.price_vs_vwap ? (
          <span className={cn("inline-flex items-center gap-0.5", row.price_vs_vwap === "ABOVE" ? "text-up" : "text-down")}>
            {row.price_vs_vwap === "ABOVE" ? <ArrowUp aria-hidden className="size-3" /> : <ArrowDown aria-hidden className="size-3" />}
            VWAP
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
        {stale ? <span className="sr-only"> (stale)</span> : null}
      </td>
    </tr>
  );
}

function SetupBadge({ setup }: { setup: SignalSetup }) {
  const long = setup.bias === "long";
  const htf = setup.against_htf;
  return (
    <span className="flex items-center gap-1.5 text-[11px]">
      <span
        className={cn("font-semibold", long ? "text-up" : "text-down")}
        title={`Entry on the last closed ${setup.trigger_timeframe} bar: SAR and 5m StochRSI agree, score ${setup.score}/5 (${setup.factors.split(",").filter(Boolean).join(", ") || "none"})`}
      >
        {long ? "Long" : "Short"} · {setup.trigger_timeframe} · {setup.score}/5
      </span>
      {htf === null ? null : (
        <span className={htf ? "text-warn" : "text-muted-foreground"}>{htf ? "against 4H" : "with 4H"}</span>
      )}
    </span>
  );
}

export function SignalCard({ item, now }: { item: SignalSymbol; now: number }) {
  return (
    <article aria-label={`Signals for ${item.symbol}`} className="border-b border-border">
      <header className="flex items-center gap-3 px-3 pt-2 pb-1">
        <SymbolLabel symbol={item.symbol} context={item.pinned} hideQuote />
        <LivePrice symbol={item.symbol} fallback={null} className="text-xs text-muted-foreground" />
        {item.setup ? <SetupBadge setup={item.setup} /> : null}
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[440px] border-collapse text-[12px]">
          <thead className="sr-only">
            <tr>
              <th scope="col">Timeframe</th><th scope="col">M trend</th><th scope="col">Last event</th>
              <th scope="col">Zone</th><th scope="col">VWAP</th>
            </tr>
          </thead>
          <tbody>
            {item.rows.map((row) => (
              <Row key={row.timeframe} row={row} now={now} />
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
