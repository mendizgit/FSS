"""Hand-checked cases for tss.domain.news (F8)."""

from tss.domain.news import MAX_TITLE, SymbolTagger, clean_title, normalize_url


def test_normalize_url_keeps_real_params_and_drops_tracking() -> None:
    raw = "HTTPS://Example.COM/a/b?id=7&utm_source=x&fbclid=abc&Utm_Medium=y&q=1#section"
    assert normalize_url(raw) == "https://example.com/a/b?id=7&q=1"
    assert normalize_url("https://example.com/a?utm_campaign=z") == "https://example.com/a"


def test_normalize_url_rejects_non_http_and_hostless() -> None:
    assert normalize_url("javascript:alert(1)") is None
    assert normalize_url("data:text/html,hi") is None
    assert normalize_url("ftp://example.com/x") is None
    assert normalize_url("https:///nohost") is None
    assert normalize_url("") is None
    assert normalize_url(None) is None


def test_two_tracking_variants_dedupe_to_one_url() -> None:
    a = normalize_url("https://site.com/post?utm_source=rss")
    b = normalize_url("https://SITE.com/post?utm_source=tw&fbclid=1#x")
    assert a == b == "https://site.com/post"


def test_clean_title() -> None:
    assert clean_title("  Bitcoin\n\t rallies \x00 today  ") == "Bitcoin rallies today"
    assert clean_title("   ") is None
    assert clean_title(None) is None
    long = "x" * 600
    out = clean_title(long)
    assert out is not None and len(out) == MAX_TITLE and out.endswith("…")


BASES = {
    "BTC": "BTC_USDT",
    "ETH": "ETH_USDT",
    "NEAR": "NEAR_USDT",
    "THE": "THE_USDT",
    "OP": "OP_USDT",
}


def test_tag_whole_word_case_sensitive() -> None:
    tagger = SymbolTagger(BASES)
    assert tagger.tag("BTC price jumps as ETH follows") == ["BTC_USDT", "ETH_USDT"]
    assert tagger.tag("btc and Eth are lowercase") == []
    assert tagger.tag("BTCUSD and ETHBTC pairs") == []  # not whole words
    assert tagger.tag("$ETH and BTC/ETH") == ["ETH_USDT", "BTC_USDT"]  # order of first appearance
    assert tagger.tag("BTC, BTC and BTC again") == ["BTC_USDT"]  # no duplicates
    assert tagger.tag("BTC-USD (BTC's rally)") == ["BTC_USDT"]


def test_tag_min_length_and_stoplist() -> None:
    assert SymbolTagger(BASES).tag("OP rally") == []  # 2-character base is never matched
    assert SymbolTagger(BASES).tag("THE NEAR PROTOCOL") == ["THE_USDT", "NEAR_USDT"]
    stopped = SymbolTagger(BASES, stoplist=["THE"])
    assert stopped.tag("THE NEAR PROTOCOL") == ["NEAR_USDT"]


def test_tag_with_no_bases() -> None:
    assert SymbolTagger({}).tag("BTC") == []


def test_parse_feed_rejects_non_feeds_but_accepts_empty_feeds() -> None:
    import pytest

    from tss.clients.rss import parse_feed
    from tss.core.errors import DataSourceError

    with pytest.raises(DataSourceError):
        parse_feed(b"<html><body>not a feed</body></html>", "X")
    with pytest.raises(DataSourceError):
        parse_feed(b"garbage", "X")
    empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'
    assert parse_feed(empty, "X") == []
    one = (
        b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
        b"<item><title>BTC up</title><link>https://x.test/a</link>"
        b"<pubDate>Mon, 05 Oct 2026 08:00:00 GMT</pubDate></item></channel></rss>"
    )
    items = parse_feed(one, "X")
    assert (items[0].title, items[0].url) == ("BTC up", "https://x.test/a")
    assert items[0].published_at is not None and items[0].published_at.hour == 8
