import json
from copy import deepcopy
from pathlib import Path

from src.inventory import SourceInventoryRecord, build_inventory_audit, read_inventory


def source(**changes: object) -> dict:
    payload = {
        "inventory_version": "1.0.0",
        "source_id": "src-example-001",
        "source_url": "https://example.org/news/1",
        "outlet": "Example outlet",
        "programme": "Example programme",
        "title": "Synthetic inventory fixture",
        "published_at": "2026-07-10T09:00:00+05:30",
        "accessed_at": "2026-07-11T10:00:00Z",
        "original_language": "en",
        "media_format": "digital_video",
        "availability": "available",
        "eligibility": "included",
        "discovery_method": "documented_query",
        "discovery_query": "synthetic query",
        "exclusion_reason": None,
        "eligible_segment_start_seconds": None,
        "eligible_segment_end_seconds": None,
        "notes": "Synthetic test only.",
    }
    payload.update(changes)
    return payload


def test_inventory_rules_for_inclusions_exclusions_and_mixed_segments() -> None:
    assert SourceInventoryRecord.model_validate(source()).eligibility.value == "included"
    excluded = source(
        source_id="src-example-002",
        source_url="https://example.org/news/2",
        eligibility="excluded",
        exclusion_reason="Outside the event scope.",
        published_at=None,
    )
    assert SourceInventoryRecord.model_validate(excluded).exclusion_reason
    mixed = source(eligible_segment_start_seconds=30, eligible_segment_end_seconds=60)
    assert SourceInventoryRecord.model_validate(mixed).eligible_segment_end_seconds == 60


def test_reader_rejects_duplicate_ids_and_urls(tmp_path: Path) -> None:
    path = tmp_path / "inventory.jsonl"
    first = source()
    duplicate_id = source(source_url="https://example.org/news/2")
    duplicate_url = source(source_id="src-example-002")
    path.write_text(
        "\n".join(map(json.dumps, (first, duplicate_id, duplicate_url))) + "\n",
        encoding="utf-8",
    )
    records, errors = read_inventory(path)
    assert len(records) == 1
    assert any("duplicate source_id" in error for error in errors)
    assert any("duplicate source_url" in error for error in errors)


def test_inventory_audit_keeps_dimensions_separate() -> None:
    included = SourceInventoryRecord.model_validate(source())
    excluded_payload = deepcopy(source())
    excluded_payload.update(
        source_id="src-example-002",
        source_url="https://example.org/news/2",
        outlet="Another outlet",
        eligibility="excluded",
        exclusion_reason="Outside scope.",
    )
    excluded = SourceInventoryRecord.model_validate(excluded_payload)
    audit = build_inventory_audit([included, excluded])
    assert audit["source_count"] == 2
    assert audit["included_count"] == 1
    assert audit["excluded_count"] == 1
    assert audit["included_by_outlet"] == {"Example outlet": 1}
    assert "expected stance" in audit["notes"][0]
