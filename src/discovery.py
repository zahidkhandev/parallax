"""Neutral, provenance-preserving discovery of candidate media sources."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from pydantic import TypeAdapter

from .inventory import SourceInventoryRecord, read_inventory

DEFAULT_ROUND = Path("methodology/collection-round-001.json")


class DiscoveryError(ValueError):
    """Raised when a discovery round cannot be safely executed."""


@dataclass(frozen=True)
class QuerySpec:
    language: str
    query: str


@dataclass(frozen=True)
class DiscoveryRun:
    records: list[SourceInventoryRecord]
    execution_log: list[dict[str, Any]]


def load_round(path: Path = DEFAULT_ROUND) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"Cannot load collection round {path}: {exc}") from exc
    required = {"round_id", "collection_start", "report_through", "query_families"}
    missing = sorted(required - payload.keys())
    if missing:
        raise DiscoveryError(f"Collection round is missing fields: {', '.join(missing)}")
    if not isinstance(payload.get("execution_log"), list):
        raise DiscoveryError("Collection round execution_log must be a list")
    return payload


def query_specs(payload: dict[str, Any]) -> list[QuerySpec]:
    specs: list[QuerySpec] = []
    for family in payload["query_families"]:
        language = TypeAdapter(str).validate_python(family["language"])
        for query in family["queries"]:
            specs.append(QuerySpec(language, TypeAdapter(str).validate_python(query)))
    if not specs:
        raise DiscoveryError("Collection round has no discovery queries")
    return specs


def google_news_feed_url(spec: QuerySpec, start: date, through: date) -> str:
    after = (start - timedelta(days=1)).isoformat()
    before = (through + timedelta(days=1)).isoformat()
    query = quote_plus(f"{spec.query} after:{after} before:{before}")
    language = "hi" if spec.language == "hi" else "en"
    return (
        f"https://news.google.com/rss/search?q={query}&hl={language}-IN"
        f"&gl=IN&ceid=IN:{language}"
    )


def fetch_feed(url: str, timeout_seconds: float = 30) -> bytes:
    request = Request(url, headers={"User-Agent": "Project-Parallax-Discovery/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return response.read()
    except OSError as exc:
        raise DiscoveryError(f"Cannot fetch discovery feed: {exc}") from exc


def _source_id(url: str) -> str:
    return f"src-{hashlib.sha256(url.encode()).hexdigest()[:20]}"


def parse_google_news_feed(
    content: bytes,
    *,
    spec: QuerySpec,
    accessed_at: datetime,
    limit: int,
) -> list[SourceInventoryRecord]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise DiscoveryError(f"Discovery feed is not valid XML: {exc}") from exc
    records: list[SourceInventoryRecord] = []
    for item in root.findall("./channel/item")[:limit]:
        url = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        source = item.find("source")
        outlet = ((source.text if source is not None else None) or "Unknown publisher").strip()
        published_text = (item.findtext("pubDate") or "").strip()
        if not url or not title:
            continue
        try:
            published_at = parsedate_to_datetime(published_text) if published_text else None
        except (TypeError, ValueError):
            published_at = None
        records.append(
            SourceInventoryRecord.model_validate(
                {
                    "inventory_version": "1.0.0",
                    "source_id": _source_id(url),
                    "source_url": url,
                    "outlet": outlet,
                    "programme": None,
                    "title": title,
                    "published_at": published_at,
                    "accessed_at": accessed_at,
                    "original_language": spec.language,
                    "media_format": "other_news_media",
                    "availability": "available",
                    "eligibility": "pending_review",
                    "discovery_method": "google_news_rss",
                    "discovery_query": spec.query,
                    "exclusion_reason": None,
                    "eligible_segment_start_seconds": None,
                    "eligible_segment_end_seconds": None,
                    "notes": (
                        "Automated candidate from a news-search RSS feed. Verify the original "
                        "publisher URL, metadata, event scope, availability, and format."
                    ),
                }
            )
        )
    return records


def execute_google_news_round(
    payload: dict[str, Any],
    *,
    through: date,
    limit: int = 100,
    now: datetime | None = None,
    feed_loader: Any = fetch_feed,
) -> DiscoveryRun:
    start = date.fromisoformat(payload["collection_start"])
    if through < start:
        raise DiscoveryError("report-through date precedes collection start")
    if not 1 <= limit <= 100:
        raise DiscoveryError("result limit must be between 1 and 100")
    accessed_at = now or datetime.now(UTC)
    records: list[SourceInventoryRecord] = []
    logs: list[dict[str, Any]] = []
    for index, spec in enumerate(query_specs(payload), 1):
        feed_url = google_news_feed_url(spec, start, through)
        content = feed_loader(feed_url)
        found = parse_google_news_feed(
            content, spec=spec, accessed_at=accessed_at, limit=limit
        )
        found = [
            record
            for record in found
            if record.published_at is not None
            and start <= record.published_at.date() <= through
        ]
        records.extend(found)
        logs.append(
            {
                "execution_id": f"{accessed_at:%Y%m%dT%H%M%SZ}-{index:03d}",
                "surface": "general web news search",
                "provider": "google_news_rss",
                "query": spec.query,
                "language": spec.language,
                "executed_at": accessed_at.isoformat().replace("+00:00", "Z"),
                "report_through": through.isoformat(),
                "requested_depth": limit,
                "retrieved_count": len(found),
                "status": "completed",
            }
        )
    return DiscoveryRun(records, logs)


def merge_inventory(
    current: list[SourceInventoryRecord], candidates: list[SourceInventoryRecord]
) -> tuple[list[SourceInventoryRecord], int]:
    merged = list(current)
    urls = {str(record.source_url) for record in current}
    added = 0
    for record in candidates:
        if str(record.source_url) in urls:
            continue
        urls.add(str(record.source_url))
        merged.append(record)
        added += 1
    return merged, added


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_discovery_results(
    *,
    round_path: Path,
    inventory_path: Path,
    payload: dict[str, Any],
    run: DiscoveryRun,
) -> tuple[int, int]:
    existing, errors = read_inventory(inventory_path)
    if errors:
        raise DiscoveryError("\n".join(errors))
    merged, added = merge_inventory(existing, run.records)
    payload["status"] = "active"
    payload["report_through"] = run.execution_log[-1]["report_through"]
    payload["date_filter"] = (
        f"{payload['collection_start']} through {payload['report_through']} inclusive"
    )
    payload["execution_log"].extend(run.execution_log)
    inventory_text = "".join(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        for record in merged
    )
    _atomic_text(inventory_path, inventory_text)
    _atomic_text(round_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return added, len(run.records)
