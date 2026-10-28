"use client";

import { useState } from "react";
import { PanelEmpty, PanelError, PanelLoading } from "@/components/layout/states";
import { Panel } from "@/components/layout/panel";
import { TimeText } from "@/components/tss/time-text";
import { usePaper, type PaperStrategy } from "@/hooks/use-queries";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PaperGroup, PaperTrade } from "@/types/api";

const usd = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
const tone = (v: number | null | undefined) =>
  !v ? "text-muted-foreground" : v > 0 ? "text-up" : "text-down";

function Stat({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="rounded-md border border-border px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className={cn("text-sm font-semibold tabular-nums", cls)}>{value}</div>
    </div>
  );
}

function Groups({ title, rows }: { title: string; rows: PaperGroup[] }) {
  return (
    <div className="min-w-[14rem] flex-1 rounded-md border border-border p-2">
      <div className="mb-1 text-xs font-semibold">{title}</div>
      {rows.length === 0 ? (
        <div className="text-xs text-muted-foreground">no closed trades</div>
      ) : (
        <table className="w-full text-xs tabular-nums">
          <tbody>
            {rows.map((g) => (
              <tr key={g.key}>
                <td className="py-0.5 pr-2">{g.key}</td>
                <td className="pr-2 text-muted-foreground">
                  {g.wins}/{g.trades} win
                </td>
                <td className={cn("pr-2 text-right", tone(g.avg_r))}>{g.avg_r.toFixed(2)}R</td>
                <td className={cn("text-right", tone(g.pnl_usdt))}>{usd(g.pnl_usdt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TradeTable({ trades, open, fgi }: { trades: PaperTrade[]; open: boolean; fgi: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs tabular-nums">
        <thead className="text-left text-muted-foreground">
          <tr>
            <th className="px-2 py-1">Symbol</th>
            <th>Side</th>
            <th>Score</th>
            {fgi ? <th>Detail</th> : <th>Flip 15m</th>}
            {fgi ? null : <th>4H</th>}
            <th>Opened</th>
            <th className="text-right">Entry</th>
            <th className="text-right">Stop</th>
            <th className="text-right">{fgi ? "TP2" : "Target"}</th>
            <th className="text-right">{open ? "Now" : "Exit"}</th>
            <th className="text-right">MFE / MAE %</th>
            <th>{open ? "" : "Reason"}</th>
            <th className="px-2 text-right">PnL</th>
            <th className="pr-2 text-right">R</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => {
            const pnl = open ? t.unrealized_usdt : t.pnl_usdt;
            return (
              <tr key={t.id} className="border-t border-border">
                <td className="px-2 py-1 font-medium">{t.symbol.replace("_USDT", "")}</td>
                <td className={t.side === "long" ? "text-up" : "text-down"}>{t.side}</td>
                <td title={t.factors ?? ""}>
                  {t.score ?? "—"}/{fgi ? 6 : 5}
                </td>
                {fgi ? (
                  <td>{t.factors}</td>
                ) : (
                  <>
                    <td title={t.flip_events ?? "no side-aligned BUY/SELL/bullT/bearT in the last 20 bars"}>
                      {t.flip_confirms ? "✓" : "—"} {t.flip_events ?? ""}
                    </td>
                    <td>{t.against_htf === null ? "—" : t.against_htf ? "against" : "with"}</td>
                  </>
                )}
                <td>
                  <TimeText iso={t.opened_at} />
                </td>
                <td className="text-right">{formatPrice(t.entry_price)}</td>
                <td className="text-right">{formatPrice(t.stop_price)}</td>
                <td className="text-right">{formatPrice(t.target_price)}</td>
                <td className="text-right">{formatPrice(open ? t.last_price : t.exit_price)}</td>
                <td className="text-right">
                  {t.mfe_pct?.toFixed(2) ?? "—"} / {t.mae_pct?.toFixed(2) ?? "—"}
                </td>
                <td>{open ? "" : t.exit_reason}</td>
                <td className={cn("px-2 text-right", tone(pnl))}>{usd(pnl)}</td>
                <td className={cn("pr-2 text-right", tone(t.r_multiple))}>
                  {t.r_multiple === null ? "" : t.r_multiple.toFixed(2)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Dummy-money test of the 15m entry alerts (no real orders, analysis only). */
export function PaperPanel() {
  const [strategy, setStrategy] = useState<PaperStrategy>("v4");
  const fgi = strategy === "fgi";
  const paper = usePaper(strategy);
  const d = paper.data;
  const s = d?.summary;
  return (
    <Panel
      title={fgi ? "Paper trading · FGI Pro strategy" : "Paper trading · 15m entry alerts (v4)"}
      subtitle={
        s && fgi
          ? `dummy money · ${s.leverage}x · ${s.margin_per_trade_usdt} USDT margin · stop capped ${s.stop_pct}% · TP1 50% · TP2 · break-even · exit on 1H trend flip`
          : s
          ? `dummy money · ${s.leverage}x · ${s.margin_per_trade_usdt} USDT margin · stop ${s.stop_pct}% · target ${s.reward_risk}R · timeout ${s.timeout_minutes} min`
          : undefined
      }
    >
      {paper.isPending ? (
        <PanelLoading />
      ) : paper.isError && !d ? (
        <PanelError error={paper.error} />
      ) : d && s ? (
        <div className="flex flex-col gap-3 p-3">
          <div className="flex gap-1 text-xs">
            {(["v4", "fgi"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setStrategy(k)}
                aria-pressed={strategy === k}
                className={cn(
                  "rounded-md border border-border px-2 py-1",
                  strategy === k ? "bg-secondary font-semibold" : "text-muted-foreground",
                )}
              >
                {k === "v4" ? "v4 entry alerts" : "FGI Pro strategy"}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
            <Stat label="Balance (USDT)" value={s.balance_usdt.toFixed(2)} cls={tone(s.realized_usdt)} />
            <Stat label="Realized" value={usd(s.realized_usdt)} cls={tone(s.realized_usdt)} />
            <Stat label="Unrealized" value={usd(s.unrealized_usdt)} cls={tone(s.unrealized_usdt)} />
            <Stat label="Open / closed" value={`${s.open_trades} / ${s.closed_trades}`} />
            <Stat label="Win rate" value={s.win_rate_pct === null ? "—" : `${s.win_rate_pct.toFixed(0)}%`} />
            <Stat label="Avg R" value={s.avg_r === null ? "—" : s.avg_r.toFixed(2)} cls={tone(s.avg_r)} />
            <Stat label="Profit factor" value={s.profit_factor === null ? "—" : s.profit_factor.toFixed(2)} />
            <Stat label="Max drawdown" value={s.max_drawdown_usdt.toFixed(2)} />
          </div>
          <div className="flex flex-wrap gap-2">
            <Groups title="By score" rows={d.by_score} />
            {fgi ? null : <Groups title="By 15m flip (BUY/SELL/bullT/bearT)" rows={d.by_flip_confirm} />}
            {fgi ? null : <Groups title="By 4H trend" rows={d.by_htf} />}
            <Groups title="By exit" rows={d.by_exit} />
            <Groups title="By side" rows={d.by_side} />
          </div>
          <section>
            <h3 className="mb-1 text-xs font-semibold">Open trades</h3>
            {d.open.length === 0 ? (
              <PanelEmpty title="No open trades" hint={fgi ? "A trade opens on each FGI signal (enable paper_fgi first)." : "A trade opens on each new 15m entry alert."} />
            ) : (
              <TradeTable trades={d.open} open fgi={fgi} />
            )}
          </section>
          <section>
            <h3 className="mb-1 text-xs font-semibold">Closed trades (latest {d.closed.length})</h3>
            {d.closed.length === 0 ? (
              <PanelEmpty title="No closed trades yet" />
            ) : (
              <TradeTable trades={d.closed} open={false} fgi={fgi} />
            )}
          </section>
        </div>
      ) : null}
    </Panel>
  );
}
