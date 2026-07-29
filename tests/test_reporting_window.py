import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from src.inventory import canonical_inventory_schema
from src.taxonomy import canonical_taxonomy
from src.validate_public_data import (
    PublicDataValidationError,
    canonical_schema,
    load_validated_dataset,
)
from tests.test_corrections import write_rows
from tests.test_manifest import manifest
from tests.test_models import valid_record


def dataset_files(tmp_path: Path, record: dict) -> tuple[Path, ...]:
    data = tmp_path / "evidence.jsonl"
    schema = tmp_path / "schema.json"
    manifest_path = tmp_path / "manifest.json"
    corrections = tmp_path / "corrections.csv"
    taxonomy = tmp_path / "taxonomy.json"
    inventory = tmp_path / "inventory.jsonl"
    inventory_schema = tmp_path / "inventory-schema.json"
    data.write_text(json.dumps(record) + "\n", encoding="utf-8")
    schema.write_text(json.dumps(canonical_schema()), encoding="utf-8")
    payload = manifest()
    payload.update(
        status="collection",
        record_count=1,
        collection_start="2026-07-01",
        collection_end=None,
    )
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    write_rows(corrections, [])
    taxonomy.write_text(json.dumps(canonical_taxonomy()), encoding="utf-8")
    inventory_record = {
        "inventory_version": "1.0.0",
        "source_id": "src-test-001",
        "source_url": record["source_url"],
        "outlet": record["outlet"],
        "programme": record["programme"],
        "title": record["title"],
        "published_at": record["published_at"] or "2026-07-20T09:00:00+05:30",
        "accessed_at": record["accessed_at"],
        "original_language": record["original_language"],
        "media_format": "digital_video",
        "availability": "available",
        "eligibility": "included",
        "discovery_method": "synthetic_test_fixture",
        "discovery_query": None,
        "exclusion_reason": None,
        "eligible_segment_start_seconds": None,
        "eligible_segment_end_seconds": None,
        "notes": "Test only.",
    }
    inventory.write_text(json.dumps(inventory_record) + "\n", encoding="utf-8")
    inventory_schema.write_text(json.dumps(canonical_inventory_schema()), encoding="utf-8")
    return data, schema, manifest_path, corrections, taxonomy, inventory, inventory_schema


def test_open_collection_includes_records_through_explicit_date(tmp_path: Path) -> None:
    record = deepcopy(valid_record())
    record["published_at"] = "2026-07-20T09:00:00+05:30"
    paths = dataset_files(tmp_path, record)
    dataset = load_validated_dataset(
        *paths[:5],
        report_through=date(2026, 7, 25),
        inventory_path=paths[5],
        inventory_schema_path=paths[6],
    )
    assert len(dataset.records) == 1
    assert dataset.report_through == date(2026, 7, 25)
    assert dataset.manifest.collection_end is None


@pytest.mark.parametrize(
    ("published_at", "message"),
    [
        ("2026-06-30T23:00:00+05:30", "outside"),
        ("2026-07-26T09:00:00+05:30", "outside"),
        (None, "published_at is required"),
    ],
)
def test_record_must_be_inside_report_window(
    tmp_path: Path, published_at: str | None, message: str
) -> None:
    record = deepcopy(valid_record())
    record["published_at"] = published_at
    paths = dataset_files(tmp_path, record)
    with pytest.raises(PublicDataValidationError, match=message):
        load_validated_dataset(
            *paths[:5],
            report_through=date(2026, 7, 25),
            inventory_path=paths[5],
            inventory_schema_path=paths[6],
        )


def test_report_through_cannot_precede_collection_start(tmp_path: Path) -> None:
    record = deepcopy(valid_record())
    record["published_at"] = "2026-07-20T09:00:00+05:30"
    paths = dataset_files(tmp_path, record)
    with pytest.raises(PublicDataValidationError, match="precedes collection_start"):
        load_validated_dataset(
            *paths[:5],
            report_through=date(2026, 6, 30),
            inventory_path=paths[5],
            inventory_schema_path=paths[6],
        )


def test_evidence_must_reference_included_inventory_source(tmp_path: Path) -> None:
    record = deepcopy(valid_record())
    record["published_at"] = "2026-07-20T09:00:00+05:30"
    paths = dataset_files(tmp_path, record)
    inventory_payload = json.loads(paths[5].read_text(encoding="utf-8"))
    inventory_payload.update(
        eligibility="excluded",
        exclusion_reason="Synthetic outside-scope decision.",
        published_at=None,
    )
    paths[5].write_text(json.dumps(inventory_payload) + "\n", encoding="utf-8")
    with pytest.raises(PublicDataValidationError, match="not an included inventory source"):
        load_validated_dataset(
            *paths[:5],
            report_through=date(2026, 7, 25),
            inventory_path=paths[5],
            inventory_schema_path=paths[6],
        )
