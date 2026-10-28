"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/lib/api-client";
import type {
  ClassificationResponse,
  DiscoveryResponse,
  HistoryResponse,
  MoversResponse,
  NewsResponse,
  PaperResponse,
  SignalsResponse,
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

export function useNews(symbol: string | null) {
  return useQuery({
    queryKey: ["news", symbol],
    queryFn: ({ signal }) =>
      apiGet<NewsResponse>(`/news?limit=60${symbol ? `&symbol=${encodeURIComponent(symbol)}` : ""}`, signal),
  });
}

export function useSignals() {
  return useQuery({
    queryKey: ["signals"],
    queryFn: ({ signal }) => apiGet<SignalsResponse>("/signals/latest", signal),
  });
}

export type PaperStrategy = "v4" | "fgi";

export function usePaper(strategy: PaperStrategy = "v4") {
  return useQuery({
    queryKey: ["paper", strategy],
    queryFn: ({ signal }) =>
      apiGet<PaperResponse>(strategy === "fgi" ? "/paper-fgi" : "/paper", signal),
    refetchInterval: 30_000,
  });
}

export function useSetFlag() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, enabled }: { key: "news" | "telegram"; enabled: boolean }) =>
      apiPost<{ flags: { news: boolean; telegram: boolean } }>(`/flags/${key}`, { enabled }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["status"] }),
  });
}

export function useRestart() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<{ requested_at: string }>("/control/restart", {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["status"] }),
  });
}

export function useSetRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) =>
      apiPost<{ paused: boolean; manual: boolean; reason: string | null }>("/control/run", { enabled }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["status"] }),
  });
}
