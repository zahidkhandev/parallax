import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from src.discovery import (
    DiscoveryError,
    QuerySpec,
    execute_google_news_round,
    google_news_feed_url,
    load_round,
    merge_inventory,
    parse_google_news_feed,
    write_discovery_results,
)
from src.inventory import read_inventory

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Synthetic NEET 2026 protest report - Test News</title>
<link>https://news.example.test/articles/one</link>
<pubDate>Wed, 15 Jul 2026 10:30:00 GMT</pubDate>
<source url="https://example.test">Test News</source></item>
<item><title>Second synthetic report - Another News</title>
<link>https://news.example.test/articles/two</link>
<pubDate>Thu, 16 Jul 2026 08:00:00 GMT</pubDate>
<source url="https://another.example.test">Another News</source></item>
</channel></rss>"""


def round_payload() -> dict[str, object]:
    return {
        "round_id": "collection-round-test",
        "collection_start": "2026-07-01",
        "report_through": "2026-07-29",
        "date_filter": "2026-07-01 through 2026-07-29 inclusive",
        "status": "planned",
        "query_families": [{"language": "en", "queries": ["NEET 2026 protest"]}],
        "execution_log": [],
    }


def test_feed_url_contains_frozen_query_and_inclusive_date_bounds() -> None:
    url = google_news_feed_url(
        QuerySpec("en", "NEET 2026 protest"), date(2026, 7, 1), date(2026, 7, 29)
    )
    assert "NEET+2026+protest" in url
    assert "after%3A2026-06-30" in url
    assert "before%3A2026-07-30" in url
    assert "ceid=IN:en" in url


def test_feed_candidates_are_pending_and_keep_discovery_provenance() -> None:
    records = parse_google_news_feed(
        FEED,
        spec=QuerySpec("en", "NEET 2026 protest"),
        accessed_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
        limit=1,
    )
    assert len(records) == 1
    assert records[0].eligibility.value == "pending_review"
    assert records[0].outlet == "Test News"
    assert records[0].discovery_query == "NEET 2026 protest"
    assert records[0].published_at == datetime(2026, 7, 15, 10, 30, tzinfo=UTC)


def test_execute_and_write_round_is_deduplicated_and_auditable(tmp_path: Path) -> None:
    now = datetime(2026, 7, 29, 12, tzinfo=UTC)
    payload = round_payload()
    run = execute_google_news_round(
        payload,
        through=date(2026, 7, 29),
        limit=100,
        now=now,
        feed_loader=lambda _: FEED,
    )
    assert run.execution_log[0]["retrieved_count"] == 2
    round_path = tmp_path / "round.json"
    inventory_path = tmp_path / "inventory.jsonl"
    round_path.write_text(json.dumps(payload), encoding="utf-8")
    inventory_path.write_text("", encoding="utf-8")

    added, retrieved = write_discovery_results(
        round_path=round_path,
        inventory_path=inventory_path,
        payload=payload,
        run=run,
    )
    records, errors = read_inventory(inventory_path)
    written_round = load_round(round_path)
    assert (added, retrieved) == (2, 2)
    assert not errors
    assert len(records) == 2
    assert written_round["status"] == "active"
    assert written_round["execution_log"][0]["provider"] == "google_news_rss"

    merged, duplicate_additions = merge_inventory(records, run.records)
    assert len(merged) == 2
    assert duplicate_additions == 0


def test_discovery_rejects_invalid_limits_and_malformed_feeds() -> None:
    with pytest.raises(DiscoveryError, match="between 1 and 100"):
        execute_google_news_round(
            round_payload(), through=date(2026, 7, 29), limit=101
        )
    with pytest.raises(DiscoveryError, match="valid XML"):
        parse_google_news_feed(
            b"not xml",
            spec=QuerySpec("en", "test"),
            accessed_at=datetime.now(UTC),
            limit=1,
        )
