"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useLiveEvents } from "@/hooks/use-live-events";
import { WsProvider } from "@/hooks/use-ws";
import { makeQueryClient } from "@/lib/query-client";

function LiveEvents() {
  useLiveEvents();
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <WsProvider>
        <TooltipProvider delay={200}>
          <LiveEvents />
          {children}
        </TooltipProvider>
      </WsProvider>
    </QueryClientProvider>
  );
}
