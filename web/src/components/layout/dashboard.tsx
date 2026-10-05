"use client";

import { useState } from "react";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ClassificationPanel } from "@/features/classification/classification-panel";
import { MoversPanel } from "@/features/movers/movers-panel";
import { NewsPanel } from "@/features/news/news-panel";
import { SignalsPanel } from "@/features/signals/signals-panel";
import { StatusBar } from "@/features/status-bar/status-bar";
import { cn } from "@/lib/utils";

type MobileTab = "classification" | "market" | "news";

/** Regions per Arch §11: >=1280 three columns; 768-1279 left + middle, news below; <768 tabs. */
export function Dashboard() {
  const [tab, setTab] = useState<MobileTab>("classification");
  const show = (id: MobileTab) => (tab === id ? "flex" : "hidden") + " md:flex";
  return (
    <div className="flex min-h-dvh min-w-0 flex-col overflow-x-hidden xl:h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-1.5 focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <StatusBar />
      <Tabs value={tab} onValueChange={(v) => setTab(v as MobileTab)} className="md:hidden">
        <TabsList className="w-full rounded-none" aria-label="Dashboard sections">
          <TabsTrigger value="classification">Classification</TabsTrigger>
          <TabsTrigger value="market">Signals / Movers</TabsTrigger>
          <TabsTrigger value="news">News</TabsTrigger>
        </TabsList>
      </Tabs>
      <main
        id="main"
        className="grid min-h-0 min-w-0 flex-1 grid-cols-[minmax(0,1fr)] gap-3 p-2 md:grid-cols-2 md:p-3 xl:grid-cols-[minmax(0,1.75fr)_minmax(0,1.4fr)_minmax(0,0.55fr)] xl:grid-rows-[minmax(0,1fr)]"
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
      <footer className="sticky bottom-0 shrink-0 border-t border-border bg-card px-3 py-1.5 text-center text-xs text-muted-foreground">
        Market analysis only — not financial advice.
      </footer>
    </div>
  );
}
