"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Tooltip around inline content. `focusable` adds a tab stop for keyboard users. */
export function Tip({
  content,
  children,
  focusable = false,
  className,
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  focusable?: boolean;
  className?: string;
}) {
  if (!content) return <>{children}</>;
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span className={cn("inline-flex", className)} tabIndex={focusable ? 0 : undefined} />}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{content}</TooltipContent>
    </Tooltip>
  );
}
