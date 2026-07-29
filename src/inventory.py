"""Validated source inventory and transparent collection coverage audit."""

from __future__ import annotations

import json
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)

DEFAULT_INVENTORY = Path("public-data/source-inventory.jsonl")
DEFAULT_INVENTORY_SCHEMA = Path("schemas/source-inventory.schema.json")


class MediaFormat(StrEnum):
    TV_REPORT = "tv_report"
    TV_DEBATE = "tv_debate"
    DIGITAL_VIDEO = "digital_video"
    INTERVIEW = "interview"
    LIVE_STREAM = "live_stream"
    ARTICLE_WITH_VIDEO = "article_with_video"
    OTHER_NEWS_MEDIA = "other_news_media"


class EligibilityStatus(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    PENDING = "pending_review"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DELETED = "deleted"
    GEO_RESTRICTED = "geo_restricted"
    UNKNOWN = "unknown"


class SourceInventoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    inventory_version: str = Field(pattern=r"^1\.0\.0$")
    source_id: str = Field(pattern=r"^src-[a-z0-9][a-z0-9._-]{2,95}$")
    source_url: HttpUrl
    outlet: str = Field(min_length=1, max_length=200)
    programme: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    published_at: AwareDatetime | None = None
    accessed_at: AwareDatetime
    original_language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$")
    media_format: MediaFormat
    availability: AvailabilityStatus
    eligibility: EligibilityStatus
    discovery_method: str = Field(min_length=1, max_length=200)
    discovery_query: str | None = Field(default=None, max_length=500)
    exclusion_reason: str | None = Field(default=None, max_length=1000)
    eligible_segment_start_seconds: float | None = Field(default=None, ge=0)
    eligible_segment_end_seconds: float | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_eligibility(self) -> SourceInventoryRecord:
        if self.eligibility is EligibilityStatus.EXCLUDED and not self.exclusion_reason:
            raise ValueError("excluded sources require exclusion_reason")
        if self.eligibility is not EligibilityStatus.EXCLUDED and self.exclusion_reason:
            raise ValueError("exclusion_reason is allowed only for excluded sources")
        if self.eligibility is EligibilityStatus.INCLUDED and self.published_at is None:
            raise ValueError("included sources require published_at")
        start, end = self.eligible_segment_start_seconds, self.eligible_segment_end_seconds
        if (start is None) != (end is None):
            raise ValueError("eligible segment start and end must be set together")
        if start is not None and end is not None and end <= start:
            raise ValueError("eligible segment end must be greater than start")
        return self


def canonical_inventory_schema() -> dict[str, Any]:
    schema = SourceInventoryRecord.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://project-parallax.example/schemas/source-inventory.schema.json"
    return schema


def validate_inventory_schema_current(path: Path = DEFAULT_INVENTORY_SCHEMA) -> None:
    try:
        checked_in = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load inventory schema {path}: {exc}") from exc
    if checked_in != canonical_inventory_schema():
        raise ValueError(f"{path} is out of date; run 'parallax inventory-schema --write'")


def read_inventory(path: Path = DEFAULT_INVENTORY) -> tuple[list[SourceInventoryRecord], list[str]]:
    records: list[SourceInventoryRecord] = []
    errors: list[str] = []
    source_ids: set[str] = set()
    urls: set[str] = set()
    try:
        handle = path.open(encoding="utf-8")
    except OSError as exc:
        return records, [f"Cannot read {path}: {exc}"]
    with handle:
        for line_number, raw in enumerate(handle, 1):
            location = f"{path}:{line_number}"
            if not raw.strip():
                errors.append(f"{location}: blank lines are not valid JSONL records")
                continue
            try:
                record = SourceInventoryRecord.model_validate_json(raw)
            except (ValidationError, ValueError) as exc:
                errors.append(f"{location}: {exc}")
                continue
            url = str(record.source_url)
            if record.source_id in source_ids:
                errors.append(f"{location}: duplicate source_id {record.source_id!r}")
                continue
            if url in urls:
                errors.append(f"{location}: duplicate source_url {url!r}")
                continue
            source_ids.add(record.source_id)
            urls.add(url)
            records.append(record)
    return records, errors


def build_inventory_audit(records: list[SourceInventoryRecord]) -> dict[str, Any]:
    def counts(attribute: str) -> dict[str, int]:
        values = Counter(str(getattr(record, attribute)) for record in records)
        return dict(sorted(values.items()))

    included = [record for record in records if record.eligibility is EligibilityStatus.INCLUDED]
    return {
        "inventory_audit_version": "1.0.0",
        "source_count": len(records),
        "included_count": len(included),
        "excluded_count": sum(
            record.eligibility is EligibilityStatus.EXCLUDED for record in records
        ),
        "pending_count": sum(record.eligibility is EligibilityStatus.PENDING for record in records),
        "by_eligibility": counts("eligibility"),
        "by_availability": counts("availability"),
        "by_media_format": counts("media_format"),
        "by_language": counts("original_language"),
        "included_by_outlet": dict(sorted(Counter(record.outlet for record in included).items())),
        "notes": [
            "Inventory inclusion is independent of expected stance or finding direction.",
            "Counts describe discovered sources and do not measure outlet quality or bias.",
        ],
    }
