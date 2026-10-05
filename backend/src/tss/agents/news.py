"""F8 News Agent: RSS -> news_items, tagged with tracked symbols (Arch §3.3)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

from tss.agents.base import PARTIAL, SUCCESS, AgentResult, BaseAgent, Deps
from tss.clients.rss import FeedItem, RssClient
from tss.core.errors import DataSourceError
from tss.db.repositories import contracts as contracts_repo
from tss.db.repositories import news as news_repo
from tss.domain.news import SymbolTagger, clean_title, normalize_url

FUTURE_TOLERANCE = timedelta(minutes=5)


class NewsAgent(BaseAgent):
    name = "news"
    critical = False

    def __init__(self, deps: Deps, rss: RssClient) -> None:
        super().__init__(deps)
        self._rss = rss

    async def run(self, cycle_id: uuid.UUID, now: datetime) -> AgentResult:
        cfg = self.deps.config
        sources = [s for s in cfg.news_sources.rss if s.enabled]
        if not sources:
            return AgentResult(status=SUCCESS, meta={"sources": {}, "note": "no enabled sources"})

        async with self.deps.session_factory() as session:
            contracts = await contracts_repo.active_contracts(session)
        tagger = SymbolTagger(
            {c.base_coin: c.symbol for c in contracts}, cfg.news_sources.symbol_stoplist
        )
        oldest = now - timedelta(days=cfg.settings.retention_days)

        results = await asyncio.gather(*(self._fetch(s.name, s.url) for s in sources))
        report: dict[str, dict[str, Any]] = {}
        rows: dict[str, dict[str, Any]] = {}
        skipped = {"bad_url": 0, "no_title": 0, "too_old": 0}
        for source, outcome in zip(sources, results, strict=True):
            if isinstance(outcome, DataSourceError):
                report[source.name] = {"status": "failed", "error": outcome.message}
                continue
            report[source.name] = {"status": "ok", "items": len(outcome)}
            for item in outcome:
                url = normalize_url(item.url)
                title = clean_title(item.title)
                if url is None:
                    skipped["bad_url"] += 1
                elif title is None:
                    skipped["no_title"] += 1
                elif item.published_at is not None and item.published_at < oldest:
                    skipped["too_old"] += 1
                elif url not in rows:  # first source wins for the same article
                    published = item.published_at
                    if published is not None and published > now + FUTURE_TOLERANCE:
                        published = None  # implausible future date: treat as unavailable
                    rows[url] = {
                        "source": source.name,
                        "title": title,
                        "url": url,
                        "published_at": published,
                        "symbols": tagger.tag(title),
                        "fetched_at": now,
                    }

        failed = sorted(n for n, r in report.items() if r["status"] == "failed")
        if len(failed) == len(sources):
            first = report[failed[0]]["error"]
            raise DataSourceError(
                self.name,
                "P3",
                "fetch_feeds",
                f"all {len(sources)} RSS sources failed; first: {first}",
                {"sources": failed},
            )

        async with self.deps.session_factory() as session:
            new = await news_repo.insert_new(session, list(rows.values()))
            await session.commit()
        for source_name in report:
            if report[source_name]["status"] == "ok":
                report[source_name]["new"] = sum(
                    1 for r in rows.values() if r["source"] == source_name
                )
        meta: dict[str, Any] = {"sources": report, "failed": failed, "new": new, "skipped": skipped}
        if cfg.settings.cryptopanic_api_key and cfg.settings.cryptopanic_api_key.get_secret_value():
            meta["cryptopanic"] = "skipped: endpoint and terms not verified (see MEMORY)"
        return AgentResult(
            status=PARTIAL if failed else SUCCESS,
            rows_in=sum(r.get("items", 0) for r in report.values()),
            rows_out=new,
            meta=meta,
            event="news_new" if new else None,
        )

    async def _fetch(self, name: str, url: str) -> list[FeedItem] | DataSourceError:
        try:
            return await self._rss.fetch(name, url)
        except DataSourceError as exc:
            self.log.warning(
                "news source failed",
                component=exc.component,
                phase=exc.phase,
                op=exc.operation,
                error=exc.message,
            )
            return exc
