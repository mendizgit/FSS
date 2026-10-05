"use client";

import { Filter, X } from "lucide-react";
import { useState } from "react";

import { Panel } from "@/components/layout/panel";
import { PanelEmpty, PanelError, PanelLoading, StaleBadge } from "@/components/layout/states";
import { TimeText } from "@/components/tss/time-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useNews, useStatus } from "@/hooks/use-queries";
import { useNow } from "@/hooks/use-now";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { NewsItem } from "@/types/api";

function baseOf(symbol: string): string {
  return symbol.split("_")[0];
}

function NewsRow({
  item,
  now,
  active,
  onFilter,
}: {
  item: NewsItem;
  now: number;
  active: string | null;
  onFilter: (symbol: string) => void;
}) {
  const when = item.published_at ?? item.fetched_at;
  return (
    <li className="flex flex-col gap-1 border-b border-border/60 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground">
        <span className="font-medium text-foreground">{item.source}</span>
        <span>{relativeTime(when, now)}</span>
        <TimeText iso={when} withDate className="num" />
        {item.published_at === null ? <span title="No publication time in the feed">(fetched)</span> : null}
      </div>
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[13px] leading-snug font-medium hover:underline"
      >
        {item.title}
      </a>
      {item.symbols.length > 0 ? (
        <div className="flex flex-wrap gap-1" aria-label="Mentioned symbols">
          {item.symbols.map((symbol) => (
            <button
              key={symbol}
              type="button"
              aria-pressed={active === symbol}
              onClick={() => onFilter(symbol)}
              title={`Show only news mentioning ${baseOf(symbol)}`}
              className={cn(
                "num rounded border px-1.5 text-[10px] leading-4 hover:bg-accent",
                active === symbol
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-secondary text-secondary-foreground",
              )}
            >
              {baseOf(symbol)}
            </button>
          ))}
        </div>
      ) : null}
    </li>
  );
}

export function NewsPanel() {
  const [filter, setFilter] = useState<string | null>(null);
  const news = useNews(filter);
  const status = useStatus();
  const now = useNow(30_000);
  const items = news.data?.items ?? [];
  const run = status.data?.runs.find((r) => r.agent === "news");
  const failed = Array.isArray(run?.meta?.failed) ? (run?.meta?.failed as string[]) : [];
  const stale = news.isError && news.data !== undefined;
  const toggle = (symbol: string) => setFilter((f) => (f === symbol ? null : symbol));

  return (
    <Panel
      title="News"
      className="flex-1"
      badge={stale ? <StaleBadge reason="The latest refresh failed; showing the last data" /> : null}
      actions={
        filter ? (
          <Button variant="outline" size="sm" onClick={() => setFilter(null)} aria-label={`Clear filter ${baseOf(filter)}`}>
            <Filter aria-hidden /> {baseOf(filter)} <X aria-hidden />
          </Button>
        ) : null
      }
    >
      {failed.length > 0 ? (
        <p role="status" className="border-b border-border bg-warn-bg px-3 py-1.5 text-xs text-warn">
          {failed.length === 1 ? "1 news source" : `${failed.length} news sources`} unavailable:{" "}
          <span className="num">{failed.join(", ")}</span>
        </p>
      ) : null}
      {news.isLoading ? (
        <PanelLoading rows={7} />
      ) : news.isError && !news.data ? (
        <PanelError error={news.error} />
      ) : items.length === 0 ? (
        filter ? (
          <PanelEmpty
            title={`No recent news mentions ${baseOf(filter)}`}
            hint={
              <Badge render={<button type="button" onClick={() => setFilter(null)} />} variant="outline">
                Clear filter
              </Badge>
            }
          />
        ) : (
          <PanelEmpty
            title="No news yet"
            hint={
              <>
                The news agent runs every 15 minutes. Next run{" "}
                <TimeText iso={status.data?.next_runs.news ?? null} />.
              </>
            }
          />
        )
      ) : (
        <ul>
          {items.map((item) => (
            <NewsRow key={item.id} item={item} now={now} active={filter} onFilter={toggle} />
          ))}
        </ul>
      )}
    </Panel>
  );
}
