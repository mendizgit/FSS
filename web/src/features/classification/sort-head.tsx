import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import type { SortState } from "@/hooks/use-sort";
import { cn } from "@/lib/utils";

export function SortHead<K extends string>({
  label,
  sortKey,
  sort,
  onSort,
  align = "right",
  title,
  sticky = false,
}: {
  label: string;
  sortKey: K;
  sort: SortState<K>;
  onSort: (key: K) => void;
  align?: "left" | "right";
  title?: string;
  sticky?: boolean;
}) {
  const active = sort.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
      className={cn(
        "sticky top-0 z-10 h-8 border-b border-border bg-card px-1.5 text-[11px] font-medium whitespace-nowrap text-muted-foreground",
        align === "right" ? "text-right" : "text-left",
        sticky && "left-0 z-20",
      )}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        title={title}
        className={cn(
          "inline-flex items-center gap-1 rounded px-0.5 hover:text-foreground",
          active && "text-foreground",
        )}
      >
        {label}
        <Icon aria-hidden className="size-3" />
      </button>
    </th>
  );
}

export function PlainHead({
  children,
  align = "right",
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      scope="col"
      className={cn(
        "sticky top-0 z-10 h-8 border-b border-border bg-card px-1.5 text-[11px] font-medium whitespace-nowrap text-muted-foreground",
        align === "right" ? "text-right" : "text-left",
      )}
    >
      {children}
    </th>
  );
}
