"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useWsClient } from "@/hooks/use-ws";
import { applyTick } from "@/lib/price-store";
import type { TssEvent } from "@/types/events";

/** Event -> query invalidation map (integration skill). Ticks only feed the price store. */
const INVALIDATIONS: Record<string, string[][]> = {
  cycle_complete: [["discovery"], ["classification"], ["history"]],
  movers_updated: [["movers"]],
  agent_status: [["status"]],
  system_state: [["status"]],
  news_new: [["news"]],
  signal_new: [["signals"]],
};

export function useLiveEvents(): void {
  const client = useWsClient();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!client) return;
    const offEvent = client.onEvent((event: TssEvent) => {
      if (event.type === "ticker") {
        applyTick(event);
        return;
      }
      for (const queryKey of INVALIDATIONS[event.type] ?? []) {
        void queryClient.invalidateQueries({ queryKey });
      }
    });
    // After a reconnect, refetch every panel once to resynchronise.
    const offResync = client.onResync(() => void queryClient.invalidateQueries());
    return () => {
      offEvent();
      offResync();
    };
  }, [client, queryClient]);
}
