"""News normalisation and symbol tagging (Arch §3.3, F8). Pure functions, no I/O."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_TITLE = 500
MIN_BASE_LEN = 3
_TRACKING_EXACT = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"})
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_SPACES = re.compile(r"\s+")


def normalize_url(raw: str | None) -> str | None:
    """Canonical article URL used for deduplication. Only http(s) with a host is accepted
    (links are rendered in the UI, so other schemes such as javascript: are rejected).
    Tracking parameters and the fragment are dropped; everything else is kept as is.
    """
    if not raw:
        return None
    parts = urlsplit(raw.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not (k.lower().startswith("utm_") or k.lower() in _TRACKING_EXACT)
        ]
    )
    netloc = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, query, ""))


def clean_title(raw: str | None) -> str | None:
    """Single-line title without control characters, capped at MAX_TITLE characters."""
    if not raw:
        return None
    text = _SPACES.sub(" ", _CONTROL.sub(" ", raw)).strip()
    if not text:
        return None
    return text if len(text) <= MAX_TITLE else text[: MAX_TITLE - 1].rstrip() + "…"


class SymbolTagger:
    """Whole-word, case-sensitive match on the base coin of active contracts.

    Bases shorter than MIN_BASE_LEN and bases in the stoplist are never matched. A word
    boundary is any character that is not A-Z, a-z or 0-9, so "$ETH" and "BTC/ETH" match
    but "BTCUSD" and "btc" do not. Returns contract symbols (e.g. BTC_USDT) in order of
    first appearance, without duplicates.
    """

    def __init__(self, base_to_symbol: Mapping[str, str], stoplist: Collection[str] = ()) -> None:
        skip = set(stoplist)
        self._symbols = {
            base: symbol
            for base, symbol in base_to_symbol.items()
            if len(base) >= MIN_BASE_LEN and base not in skip
        }
        self._pattern: re.Pattern[str] | None = None
        if self._symbols:
            alternatives = "|".join(
                re.escape(b) for b in sorted(self._symbols, key=lambda b: (-len(b), b))
            )
            self._pattern = re.compile(rf"(?<![A-Za-z0-9])(?:{alternatives})(?![A-Za-z0-9])")

    def tag(self, title: str) -> list[str]:
        if self._pattern is None:
            return []
        seen: dict[str, None] = {}
        for match in self._pattern.finditer(title):
            seen.setdefault(self._symbols[match.group(0)], None)
        return list(seen)
