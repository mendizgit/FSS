import type { AgentRun, StatusResponse } from "@/types/api";

export interface ChipSpec {
  id: string;
  label: string;
  /** agent_runs.agent that backs this chip; null = module not enabled yet */
  agent: string | null;
  nextKey: string | null;
  note?: string;
}

export const CHIPS: ChipSpec[] = [
  { id: "universe", label: "Universe", agent: "universe", nextKey: "universe" },
  { id: "snapshots", label: "Snapshots", agent: "snapshot", nextKey: "snapshot" },
  { id: "movers", label: "Movers", agent: "movers", nextKey: "snapshot" },
  {
    id: "pipeline",
    label: "Pipeline",
    agent: "pipeline",
    nextKey: "pipeline",
    note: "Kline sync → Pool → Selection → Classification",
  },
  { id: "news", label: "News", agent: "news", nextKey: "news", note: "RSS sources, every 15 min" },
  { id: "signals", label: "Signals", agent: null, nextKey: null, note: "Phase 4" },
];

export const PIPELINE_STEPS = ["kline_sync", "momentum", "classification"] as const;

export function runFor(status: StatusResponse | undefined, agent: string | null): AgentRun | null {
  if (!status || !agent) return null;
  return status.runs.find((r) => r.agent === agent) ?? null;
}

export type Tone = "up" | "warn" | "crit" | "info" | "muted";

export function toneForStatus(status: string | undefined): Tone {
  switch (status) {
    case "SUCCESS":
      return "up";
    case "PARTIAL":
      return "warn";
    case "FAILED":
    case "HALTED":
      return "crit";
    case "RUNNING":
      return "info";
    default:
      return "muted";
  }
}

export const TONE_TEXT: Record<Tone, string> = {
  up: "text-up",
  warn: "text-warn",
  crit: "text-crit",
  info: "text-info",
  muted: "text-muted-foreground",
};

export const TONE_DOT: Record<Tone, string> = {
  up: "bg-up",
  warn: "bg-warn",
  crit: "bg-crit",
  info: "bg-info",
  muted: "bg-muted-foreground",
};
