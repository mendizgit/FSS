import { AlertTriangle, Hourglass, Inbox, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";

export function PanelLoading({ rows = 6 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2 p-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-7 w-full" />
      ))}
    </div>
  );
}

function Message({
  icon: Icon,
  title,
  hint,
  tone = "muted",
}: {
  icon: typeof Inbox;
  title: string;
  hint?: React.ReactNode;
  tone?: "muted" | "warn" | "crit";
}) {
  const color =
    tone === "crit" ? "text-crit" : tone === "warn" ? "text-warn" : "text-muted-foreground";
  return (
    <div className="flex flex-col items-center gap-1 px-4 py-8 text-center" role="status">
      <Icon aria-hidden className={`size-5 ${color}`} />
      <p className="text-sm font-medium">{title}</p>
      {hint ? <p className="max-w-sm text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function PanelEmpty({ title, hint }: { title: string; hint?: React.ReactNode }) {
  return <Message icon={Inbox} title={title} hint={hint} />;
}

export function PanelWarming({ title, hint }: { title: string; hint?: React.ReactNode }) {
  return <Message icon={Hourglass} title={title} hint={hint} tone="warn" />;
}

export function PanelModuleOff({ title, hint }: { title: string; hint?: React.ReactNode }) {
  return <Message icon={Inbox} title={title} hint={hint} />;
}

/** Error state: always names the component that failed. */
export function PanelError({ error }: { error: unknown }) {
  const apiError = error instanceof ApiError ? error : null;
  const offline = apiError?.code === "network";
  return (
    <Message
      icon={offline ? WifiOff : AlertTriangle}
      tone="crit"
      title={offline ? "Cannot reach the API" : "This panel failed to load"}
      hint={
        <>
          <span className="num">{apiError?.component ?? "dashboard"}</span>:{" "}
          {apiError?.message ?? "unexpected error"}
        </>
      }
    />
  );
}

/** Shown when a refetch failed but older data is still displayed. */
export function StaleBadge({ reason }: { reason?: string }) {
  return (
    <Badge variant="outline" className="border-warn/50 bg-warn-bg text-warn" title={reason}>
      <AlertTriangle aria-hidden /> stale
    </Badge>
  );
}
