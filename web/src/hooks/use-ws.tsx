"use client";

import { createContext, useContext, useEffect, useState, useSyncExternalStore } from "react";

import { defaultWsUrl, WsClient, type WsStatus } from "@/lib/ws-client";

const WsContext = createContext<WsClient | null>(null);

export function WsProvider({ children }: { children: React.ReactNode }) {
  // Created once per tab on the client (null during SSR); connection opens in the effect.
  const [client] = useState<WsClient | null>(() =>
    typeof window === "undefined" ? null : new WsClient(defaultWsUrl()),
  );

  useEffect(() => {
    client?.start();
    return () => client?.stop();
  }, [client]);

  return <WsContext.Provider value={client}>{children}</WsContext.Provider>;
}

export function useWsClient(): WsClient | null {
  return useContext(WsContext);
}

const noopSubscribe = () => () => {};

export function useWsStatus(): WsStatus {
  const client = useWsClient();
  return useSyncExternalStore(
    client ? client.onStatus : noopSubscribe,
    client ? client.getStatus : () => "connecting" as WsStatus,
    () => "connecting" as WsStatus,
  );
}
