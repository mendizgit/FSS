"use client";

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api-client";
import type {
  ClassificationResponse,
  DiscoveryResponse,
  HistoryResponse,
  MoversResponse,
  StatusResponse,
  WindowId,
} from "@/types/api";

export function useStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: ({ signal }) => apiGet<StatusResponse>("/status", signal),
  });
}

export function useDiscovery() {
  return useQuery({
    queryKey: ["discovery"],
    queryFn: ({ signal }) => apiGet<DiscoveryResponse>("/discovery/latest", signal),
  });
}

export function useClassification(window: WindowId) {
  return useQuery({
    queryKey: ["classification", window],
    queryFn: ({ signal }) =>
      apiGet<ClassificationResponse>(`/classification/latest?window=${window}`, signal),
  });
}

export function useMovers() {
  return useQuery({
    queryKey: ["movers"],
    queryFn: ({ signal }) => apiGet<MoversResponse>("/movers/latest", signal),
  });
}

export function useHistory(symbol: string | null, window: WindowId) {
  return useQuery({
    queryKey: ["history", symbol, window],
    queryFn: ({ signal }) =>
      apiGet<HistoryResponse>(
        `/classification/${encodeURIComponent(symbol ?? "")}/history?window=${window}&hours=24`,
        signal,
      ),
    enabled: symbol !== null,
  });
}
