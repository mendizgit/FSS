// The backend sends UTC ISO-8601. This is the only place that converts to IST (display only).

const IST = "Asia/Kolkata";

const timeFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: IST,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});
const dateTimeFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: IST,
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const utcFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatIstTime(iso: string | null | undefined): string {
  const d = parse(iso);
  return d ? `${timeFmt.format(d)} IST` : "—";
}

export function formatIstDateTime(iso: string | null | undefined): string {
  const d = parse(iso);
  return d ? `${dateTimeFmt.format(d)} IST` : "—";
}

/** Tooltip text: the same instant in UTC. */
export function formatUtc(iso: string | null | undefined): string {
  const d = parse(iso);
  return d ? `${utcFmt.format(d)} UTC` : "";
}

export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  const d = parse(iso);
  if (!d) return "—";
  const s = Math.round((now - d.getTime()) / 1000);
  const abs = Math.abs(s);
  const unit =
    abs < 60 ? `${abs}s` : abs < 3600 ? `${Math.round(abs / 60)}m` : `${Math.round(abs / 3600)}h`;
  return s >= 0 ? `${unit} ago` : `in ${unit}`;
}

export function durationSeconds(start: string | null, end: string | null): number | null {
  const a = parse(start);
  const b = parse(end);
  return a && b ? (b.getTime() - a.getTime()) / 1000 : null;
}
