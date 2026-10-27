"use client";

import { PanelRightClose, PanelRightOpen, RotateCw } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ClassificationPanel } from "@/features/classification/classification-panel";
import { MoversPanel } from "@/features/movers/movers-panel";
import { NewsPanel } from "@/features/news/news-panel";
import { SignalsPanel } from "@/features/signals/signals-panel";
import { useRestart, useSetFlag, useSetRun, useStatus } from "@/hooks/use-queries";
import { StatusBar } from "@/features/status-bar/status-bar";
import { cn } from "@/lib/utils";

const NEWS_KEY = "tss-news-open";
const newsListeners = new Set<() => void>();
let memoryNewsOpen: boolean | null = null; // fallback when localStorage is unavailable

function readNewsOpen(): boolean {
  if (memoryNewsOpen !== null) return memoryNewsOpen;
  try {
    return localStorage.getItem(NEWS_KEY) !== "0";
  } catch {
    return true;
  }
}

function subscribeNews(listener: () => void): () => void {
  newsListeners.add(listener);
  return () => {
    newsListeners.delete(listener);
  };
}

type MobileTab = "classification" | "market" | "news";

/** Regions per Arch §11: >=1280 three columns; 768-1279 left + middle, news below; <768 tabs. */
export function Dashboard() {
  const [tab, setTab] = useState<MobileTab>("classification");
  const newsOpen = useSyncExternalStore(subscribeNews, readNewsOpen, () => true);
  const toggleNews = () => {
    const next = !newsOpen;
    memoryNewsOpen = next;
    try {
      localStorage.setItem(NEWS_KEY, next ? "1" : "0");
    } catch {
      // storage unavailable: the choice applies to this tab only
    }
    newsListeners.forEach((l) => l());
  };
  const show = (id: MobileTab) =>
    (tab === id ? "flex" : "hidden") + (id === "news" && !newsOpen ? " md:hidden" : " md:flex");
  const status = useStatus().data;
  const setFlag = useSetFlag();
  const setRun = useSetRun();
  const restart = useRestart();
  const flags = status?.flags;
  const flagButton = (key: "news" | "telegram", label: string, on: boolean, disabled: boolean) => (
    <Button
      variant="outline"
      size="sm"
      disabled={disabled || setFlag.isPending}
      onClick={() => setFlag.mutate({ key, enabled: !on })}
      aria-pressed={on}
      title={
        key === "news"
          ? on ? "News collection is on. Click to stop fetching feeds." : "News collection is stopped. Click to resume."
          : disabled ? "Telegram credentials are not set in .env" : on ? "Telegram alerts are on. Click to pause." : "Telegram alerts are off. Click to resume."
      }
    >
      <span aria-hidden className={cn("size-2 rounded-full", on ? "bg-up" : "bg-muted-foreground")} />
      {label}: {on ? "on" : "off"}
    </Button>
  );
  const NewsIcon = newsOpen ? PanelRightClose : PanelRightOpen;
  return (
    <div className="flex min-h-dvh min-w-0 flex-col overflow-x-hidden xl:h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-1.5 focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <StatusBar
        leading={
          <Button
            variant="outline"
            size="sm"
            disabled={restart.isPending}
            onClick={() => {
              if (window.confirm("Restart the system? Breakers and halt state are reset and the startup sequence runs again.")) restart.mutate();
            }}
            title="Full system restart: resets breakers, halt and degraded state, then re-runs universe, snapshot and pipeline."
          >
            <RotateCw aria-hidden className={restart.isPending ? "animate-spin" : undefined} />
            Restart
          </Button>
        }
        actions={
          <>
          {status ? (
            <Button
              variant="outline"
              size="sm"
              disabled={setRun.isPending}
              onClick={() => setRun.mutate(status.pause.paused)}
              title={
                status.pause.paused
                  ? `${status.pause.reason ?? "Paused"}. Click to start now: it runs until 00:00 IST.`
                  : status.pause.manual
                    ? `${status.pause.reason ?? "Running"}. Click to pause until 05:00 IST.`
                    : "Running. Click to pause until 05:00 IST (it also pauses automatically at 00:00 IST)."
              }
            >
              <span aria-hidden className={cn("size-2 rounded-full", status.pause.paused ? "bg-muted-foreground" : "bg-up")} />
              {status.pause.paused ? "Start system" : "Pause system"}
            </Button>
          ) : null}
          {flags ? flagButton("news", "News feed", flags.news, false) : null}
          {flags ? flagButton("telegram", "Telegram", flags.telegram, !status?.telegram_configured) : null}
          <Button
            variant="ghost"
            size="sm"
            className="max-md:hidden"
            onClick={toggleNews}
            aria-pressed={!newsOpen}
            aria-label={newsOpen ? "Hide News panel" : "Show News panel"}
          >
            <NewsIcon aria-hidden />
            News
          </Button>
          </>
        }
      />
      <Tabs value={tab} onValueChange={(v) => setTab(v as MobileTab)} className="md:hidden">
        <TabsList className="w-full rounded-none" aria-label="Dashboard sections">
          <TabsTrigger value="classification">Classification</TabsTrigger>
          <TabsTrigger value="market">Signals / Movers</TabsTrigger>
          <TabsTrigger value="news">News</TabsTrigger>
        </TabsList>
      </Tabs>
      <main
        id="main"
        className={cn(
          "grid min-h-0 min-w-0 flex-1 grid-cols-[minmax(0,1fr)] gap-3 p-2 md:grid-cols-2 md:p-3 ",
          newsOpen
            ? "xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1.5fr)_minmax(0,0.55fr)]"
            : "xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]",
          "xl:grid-rows-[minmax(0,1fr)]",
        )}
      >
        <div className={cn("min-h-0 min-w-0 flex-col max-md:min-h-[60dvh] md:max-xl:h-[78dvh]", show("classification"))}>
          <ClassificationPanel />
        </div>
        <div className={cn("min-h-0 min-w-0 flex-col gap-3 md:max-xl:h-[78dvh]", show("market"))}>
          <SignalsPanel />
          <MoversPanel />
        </div>
        <div className={cn("min-h-0 min-w-0 flex-col md:col-span-2 md:max-xl:h-72 xl:col-span-1", show("news"))}>
          <NewsPanel />
        </div>
      </main>
    </div>
  );
}
