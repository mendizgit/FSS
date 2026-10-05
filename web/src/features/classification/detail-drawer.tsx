"use client";

import { Change } from "@/components/tss/change";
import { LivePrice } from "@/components/tss/live-price";
import { TimeText } from "@/components/tss/time-text";
import { PanelError } from "@/components/layout/states";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useHistory } from "@/hooks/use-queries";
import { formatFunding, formatFundingDelta, formatUsdCompact } from "@/lib/format";
import type { WindowId } from "@/types/api";

import type { ClassificationViewRow } from "./classification-table";
import { FlagChips } from "./flag-chips";
import { FLAG_META, reasonText } from "./meta";
import { Sparkline } from "./sparkline";
import { StateBadge } from "./state-badge";

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

export function DetailDrawer({
  row,
  window,
  onClose,
}: {
  row: ClassificationViewRow | null;
  window: WindowId;
  onClose: () => void;
}) {
  const history = useHistory(row?.symbol ?? null, window);
  const points = history.data?.points ?? [];
  return (
    <Sheet open={row !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full gap-3 overflow-y-auto sm:max-w-md">
        {row ? (
          <>
            <SheetHeader>
              <SheetTitle className="flex flex-wrap items-center gap-2">
                <span className="text-base">{row.symbol.replace("_", " / ")}</span>
                <StateBadge state={row.state} tooltip={false} />
              </SheetTitle>
              <SheetDescription>
                {window} window · updated <TimeText iso={row.ts} />
                {row.pinned ? " · market context" : ""}
              </SheetDescription>
            </SheetHeader>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-4">
              <Metric label="Price">
                <LivePrice symbol={row.symbol} fallback={row.last_price} />
              </Metric>
              <Metric label="Last 15m bar">
                <Change value={row.price_change_15m_pct} />
              </Metric>
              <Metric label={`Price Δ ${window}`}>
                <Change value={row.price_change_pct} />
              </Metric>
              <Metric label="Open interest">
                <span className="num">{formatUsdCompact(row.oi_notional_usdt)}</span>
              </Metric>
              <Metric label={`OI Δ ${window}`}>
                <Change value={row.oi_change_pct} />
              </Metric>
              <Metric label={`Futures volume Δ ${window}`}>
                <Change value={row.fut_volume_change_pct} digits={1} />
              </Metric>
              <Metric label={`Spot volume Δ ${window}`}>
                {row.spot_volume_change_pct === null ? (
                  <span className="text-muted-foreground">no spot data</span>
                ) : (
                  <Change value={row.spot_volume_change_pct} digits={1} />
                )}
              </Metric>
              <Metric label="Funding / Δ">
                <span className="num">
                  {formatFunding(row.funding_now)} / {formatFundingDelta(row.funding_delta)}
                </span>
              </Metric>
            </dl>

            <section className="flex flex-col gap-1.5 px-4" aria-label="Flags">
              <h3 className="text-xs font-semibold">Flags</h3>
              <FlagChips flags={row.flags} includeAlways />
              <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                {row.flags.map((f) => (
                  <li key={f}>
                    <span className="num text-foreground">{FLAG_META[f]?.abbr ?? f}</span>{" "}
                    {FLAG_META[f]?.meaning}
                  </li>
                ))}
              </ul>
            </section>

            {row.unreliable_reasons.length > 0 ? (
              <section className="flex flex-col gap-1 px-4" aria-label="Why unreliable">
                <h3 className="text-xs font-semibold text-warn">Why unreliable</h3>
                <ul className="list-disc pl-4 text-xs text-muted-foreground">
                  {row.unreliable_reasons.map((r) => (
                    <li key={r}>{reasonText(r)}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section className="flex flex-col gap-2 px-4 pb-4" aria-label="History">
              <h3 className="text-xs font-semibold">Last 24 h ({window} window)</h3>
              {history.isLoading ? (
                <Skeleton className="h-28 w-full" />
              ) : history.isError && points.length === 0 ? (
                <PanelError error={history.error} />
              ) : (
                <>
                  <div>
                    <p className="text-[11px] text-muted-foreground">Price Δ {window} (%)</p>
                    <Sparkline values={points.map((p) => p.price_change_pct)} label="price change" />
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground">OI Δ {window} (%)</p>
                    <Sparkline values={points.map((p) => p.oi_change_pct)} label="open-interest change" />
                  </div>
                  <ol className="flex flex-col gap-1 text-xs">
                    {points.slice(-6).reverse().map((p) => (
                      <li key={p.ts} className="flex items-center justify-between gap-2">
                        <TimeText iso={p.ts} className="num text-muted-foreground" />
                        <StateBadge state={p.state} tooltip={false} />
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </section>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
