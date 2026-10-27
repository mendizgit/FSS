"use client";

import type { ReactNode } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2, Hourglass, Radio, WifiOff } from "lucide-react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Tip } from "@/components/tss/tip";
import { TimeText } from "@/components/tss/time-text";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useStatus } from "@/hooks/use-queries";
import { useTickAgeSeconds } from "@/hooks/use-tick-age";
import { useWsStatus } from "@/hooks/use-ws";
import { formatBytes } from "@/lib/format";
import { durationSeconds } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { AgentRun, StatusResponse } from "@/types/api";

import {
  CHIPS,
  type ChipSpec,
  PIPELINE_STEPS,
  runFor,
  TONE_DOT,
  TONE_TEXT,
  toneForStatus,
} from "./agent-chips";

function SystemState({ status, error }: { status: StatusResponse | undefined; error: boolean }) {
  const state = error && !status ? "UNREACHABLE" : (status?.state ?? "LOADING");
  const config: Record<string, { icon: typeof Radio; text: string; tone: string }> = {
    RUNNING: { icon: CheckCircle2, text: "Running", tone: "border-up/50 text-up bg-up-bg" },
    WARMING_UP: { icon: Hourglass, text: "Warming up", tone: "border-warn/50 text-warn bg-warn-bg" },
    DEGRADED: { icon: AlertTriangle, text: "Degraded", tone: "border-warn/50 text-warn bg-warn-bg" },
    PAUSED: { icon: Hourglass, text: "Paused", tone: "border-border text-muted-foreground" },
    HALTED: { icon: AlertOctagon, text: "Halted", tone: "border-crit/60 text-crit bg-crit-bg" },
    UNKNOWN: { icon: AlertTriangle, text: "No worker data", tone: "border-warn/50 text-warn bg-warn-bg" },
    UNREACHABLE: { icon: WifiOff, text: "API unreachable", tone: "border-crit/60 text-crit bg-crit-bg" },
    LOADING: { icon: Hourglass, text: "Loading", tone: "border-border text-muted-foreground" },
  };
  const c = config[state] ?? config.UNKNOWN;
  const Icon = c.icon;
  return (
    <Tip content={status?.reason ?? (error ? "The dashboard cannot reach the API" : undefined)} focusable>
      <span
        className={cn(
          "inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-xs font-medium",
          c.tone,
        )}
      >
        <Icon aria-hidden className="size-3.5" />
        {c.text}
      </span>
    </Tip>
  );
}

function WsIndicator() {
  const ws = useWsStatus();
  const map = {
    open: { icon: Radio, text: "Live", tone: "text-up" },
    connecting: { icon: Radio, text: "Connecting", tone: "text-warn" },
    closed: { icon: WifiOff, text: "Offline: retrying", tone: "text-crit" },
  } as const;
  const m = map[ws];
  const Icon = m.icon;
  const age = useTickAgeSeconds();
  const tickText = age === null ? "no price tick yet" : age <= 1 ? "last price tick just now" : `last price tick ${age}s ago`;
  return (
    <Tip content={`Live updates over WebSocket: ${tickText}. Prices tick about once a second; analysis panels refresh as soon as the backend finishes a cycle.`} focusable>
      <span className={cn("inline-flex items-center gap-1 text-xs font-medium", m.tone)}>
        <Icon aria-hidden className="size-3.5" />
        {m.text}
      </span>
    </Tip>
  );
}

function NewsSources({ meta }: { meta: Record<string, unknown> }) {
  const sources = (meta.sources ?? {}) as Record<string, { status?: string; items?: number; new?: number; error?: string }>;
  const entries = Object.entries(sources);
  if (entries.length === 0) return null;
  return (
    <ul className="flex flex-col gap-0.5 border-t border-border pt-2">
      {entries.map(([name, s]) => (
        <li key={name} className="flex justify-between gap-2">
          <span className="text-muted-foreground">{name}</span>
          <span className={s.status === "ok" ? "text-up" : "text-crit"} title={s.error}>
            {s.status === "ok" ? `${s.items ?? 0} items · ${s.new ?? 0} new` : "failed"}
          </span>
        </li>
      ))}
    </ul>
  );
}

function RunDetails({ spec, status, run }: { spec: ChipSpec; status: StatusResponse; run: AgentRun | null }) {
  const next = spec.nextKey ? status.next_runs[spec.nextKey] : null;
  const duration = run ? durationSeconds(run.started_at, run.finished_at) : null;
  const steps = spec.id === "pipeline" ? PIPELINE_STEPS.map((s) => runFor(status, s)) : [];
  return (
    <div className="flex flex-col gap-2 text-xs">
      <p className="text-sm font-semibold">{spec.label}</p>
      {spec.note ? <p className="text-muted-foreground">{spec.note}</p> : null}
      {spec.needsTelegram && status.telegram_paused ? (
        <p className="rounded border border-border bg-muted p-2 text-muted-foreground">
          Paused. Use the Telegram button in the header to resume (it overrides{" "}
          <span className="num">TELEGRAM_ALERTS</span> in <span className="num">.env</span>).
        </p>
      ) : spec.needsTelegram && !status.telegram_configured ? (
        <p className="rounded border border-border bg-muted p-2 text-muted-foreground">
          Not configured. Set <span className="num">TELEGRAM_BOT_TOKEN</span> and{" "}
          <span className="num">TELEGRAM_CHAT_ID</span> in <span className="num">.env</span> (see the
          README, “Telegram alerts”), then restart the worker.
        </p>
      ) : run ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          <dt className="text-muted-foreground">Status</dt>
          <dd className={TONE_TEXT[toneForStatus(run.status)]}>{run.status}</dd>
          <dt className="text-muted-foreground">Last run</dt>
          <dd><TimeText iso={run.started_at} /></dd>
          <dt className="text-muted-foreground">Duration</dt>
          <dd className="num">{duration === null ? "—" : `${duration.toFixed(1)} s`}</dd>
          <dt className="text-muted-foreground">Rows in / out</dt>
          <dd className="num">{run.rows_in ?? "—"} / {run.rows_out ?? "—"}</dd>
          {run.selected_count !== null ? (
            <>
              <dt className="text-muted-foreground">Selected</dt>
              <dd className="num">{run.selected_count}</dd>
            </>
          ) : null}
          <dt className="text-muted-foreground">Next run</dt>
          <dd>{next ? <TimeText iso={next} /> : "—"}</dd>
        </dl>
      ) : (
        <p className="text-muted-foreground">
          {spec.agent ? "No run recorded yet." : `Not enabled (${spec.note}).`}
        </p>
      )}
      {steps.length > 0 ? (
        <ul className="flex flex-col gap-0.5 border-t border-border pt-2">
          {PIPELINE_STEPS.map((name, i) => (
            <li key={name} className="flex justify-between gap-2">
              <span className="num text-muted-foreground">{name}</span>
              <span className={TONE_TEXT[toneForStatus(steps[i]?.status)]}>
                {steps[i]?.status ?? "—"}
                {steps[i]?.selected_count != null ? ` · ${steps[i]?.selected_count} sel` : ""}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {spec.id === "news" && run?.meta ? <NewsSources meta={run.meta} /> : null}
      {spec.id === "telegram" && run?.meta ? (
        <p className="border-t border-border pt-2 text-muted-foreground">
          Last run: sent <span className="num text-foreground">{String(run.meta.sent ?? 0)}</span>, retrying{" "}
          <span className="num text-foreground">{String(run.meta.released ?? 0)}</span>
        </p>
      ) : null}
      {run?.error_message ? (
        <p role="alert" className="rounded border border-crit/50 bg-crit-bg p-2 text-crit">
          <span className="num font-semibold">{run.error_component ?? "unknown"}</span>:{" "}
          {run.error_message}
        </p>
      ) : null}
    </div>
  );
}

function AgentChip({ spec, status }: { spec: ChipSpec; status: StatusResponse | undefined }) {
  const run = runFor(status, spec.agent);
  const off = spec.agent === null || (spec.needsTelegram === true && (status?.telegram_configured === false || status?.telegram_paused === true));
  const tone = off ? "muted" : toneForStatus(run?.status);
  const duration = run ? durationSeconds(run.started_at, run.finished_at) : null;
  const next = status && spec.nextKey ? status.next_runs[spec.nextKey] : null;
  const pipelineSelected =
    spec.id === "pipeline" ? runFor(status, "classification")?.selected_count : run?.selected_count;
  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-card px-2 text-xs whitespace-nowrap hover:bg-muted",
          off && "opacity-70",
        )}
        aria-label={`${spec.label}: ${off ? "not configured" : (run?.status ?? "no run yet")}. Open details`}
      >
        <span aria-hidden className={cn("size-2 rounded-full", TONE_DOT[tone])} />
        <span className="font-medium">{spec.label}</span>
        <span className={TONE_TEXT[tone]}>{off ? "off" : (run?.status ?? "—")}</span>
        {run && !off ? (
          <span className="num hidden text-muted-foreground lg:inline">
            {duration !== null ? `${duration.toFixed(1)}s` : ""}
            {run.rows_out !== null ? ` · ${run.rows_out}` : ""}
            {pipelineSelected != null ? ` · sel ${pipelineSelected}` : ""}
          </span>
        ) : null}
        {run && !off ? <TimeText iso={run.started_at} className="num hidden text-muted-foreground xl:inline" /> : null}
        {next && !off ? (
          <span className="hidden text-muted-foreground 2xl:inline">
            next <TimeText iso={next} />
          </span>
        ) : null}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80">
        {status ? <RunDetails spec={spec} status={status} run={run} /> : <p className="text-xs">Loading…</p>}
      </PopoverContent>
    </Popover>
  );
}

export function StatusBar({ actions, leading }: { actions?: ReactNode; leading?: ReactNode }) {
  const query = useStatus();
  const status = query.data;
  return (
    <header className="shrink-0 border-b border-border bg-card px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {leading}
        <h1 className="text-sm font-semibold tracking-tight">Trading Signal System</h1>
        <SystemState status={status} error={query.isError} />
        {status ? (
          <p className="num flex items-center gap-3 text-xs text-muted-foreground">
            <span>
              Universe <span className="text-foreground">{status.universe.active.toLocaleString("en-US")}</span>
            </span>
            <span>
              Liquid <span className="text-foreground">{status.universe.liquid.toLocaleString("en-US")}</span>
            </span>
            <span className="hidden sm:inline">DB {formatBytes(status.db_size_bytes)}</span>
          </p>
        ) : null}
        {query.isError && status ? (
          <span className="text-xs text-warn">status stale: last refresh failed</span>
        ) : null}
        <div className="ml-auto flex items-center gap-3">
          <WsIndicator />
          {actions}
          <ThemeToggle />
        </div>
      </div>
      <nav aria-label="Agents" className="mt-2 flex flex-wrap gap-1.5">
        {CHIPS.map((spec) => (
          <AgentChip key={spec.id} spec={spec} status={status} />
        ))}
      </nav>
    </header>
  );
}
