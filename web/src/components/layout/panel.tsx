import { cn } from "@/lib/utils";

/** Card shell for one dashboard panel. The body scrolls inside the panel, never the page. */
export function Panel({
  title,
  subtitle,
  actions,
  badge,
  className,
  bodyClassName,
  children,
}: {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  badge?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card text-card-foreground",
        className,
      )}
    >
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        {badge}
        {subtitle ? <p className="text-xs text-muted-foreground">{subtitle}</p> : null}
        {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
      </header>
      <div className={cn("min-h-0 flex-1 overflow-auto", bodyClassName)}>{children}</div>
    </section>
  );
}
