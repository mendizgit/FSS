"""RSS client (feedparser). Reads title, link and publication time only (Arch §3.3, F8)."""

from __future__ import annotations

import asyncio
import calendar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import feedparser

from tss.clients.http import PHASE, HttpClient
from tss.core.errors import DataSourceError

COMPONENT = "rss"


@dataclass(frozen=True)
class FeedItem:
    title: str | None
    url: str | None
    published_at: datetime | None


def _published(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)


def parse_feed(payload: bytes, source: str) -> list[FeedItem]:
    """Parse a feed body. A body that is not a feed (no entries and malformed or of an unknown
    type, e.g. an HTML error page) is an error; an empty but valid feed is an empty list.
    """
    feed = feedparser.parse(payload)
    if not feed.entries and (feed.bozo or not feed.version):
        raise DataSourceError(
            COMPONENT,
            PHASE,
            source,
            f"{source} did not return a valid RSS/Atom feed",
            {"source": source},
        )
    return [
        FeedItem(title=entry.get("title"), url=entry.get("link"), published_at=_published(entry))
        for entry in feed.entries
    ]


class RssClient:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def fetch(self, name: str, url: str) -> list[FeedItem]:
        payload = await self._http.get_bytes(url, component=COMPONENT, operation=name)
        return await asyncio.to_thread(parse_feed, payload, name)
