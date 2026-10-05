import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api-client";

/** WS events are the primary refresh trigger; the 60 s interval is only a fallback. */
export const FALLBACK_REFETCH_MS = 60_000;

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchInterval: FALLBACK_REFETCH_MS,
        refetchOnWindowFocus: false,
        retry: (count, error) => !(error instanceof ApiError && error.status === 401) && count < 1,
      },
    },
  });
}
