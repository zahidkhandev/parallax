import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from src.taxonomy import canonical_taxonomy
from src.validate_public_data import (
    PublicDataValidationError,
    canonical_schema,
    load_validated_dataset,
)
from tests.test_corrections import write_rows
from tests.test_manifest import manifest
from tests.test_models import valid_record


def dataset_files(tmp_path: Path, record: dict) -> tuple[Path, Path, Path, Path, Path]:
    data = tmp_path / "evidence.jsonl"
    schema = tmp_path / "schema.json"
    manifest_path = tmp_path / "manifest.json"
    corrections = tmp_path / "corrections.csv"
    taxonomy = tmp_path / "taxonomy.json"
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
    return data, schema, manifest_path, corrections, taxonomy


def test_open_collection_includes_records_through_explicit_date(tmp_path: Path) -> None:
    record = deepcopy(valid_record())
    record["published_at"] = "2026-07-20T09:00:00+05:30"
    paths = dataset_files(tmp_path, record)
    dataset = load_validated_dataset(*paths, report_through=date(2026, 7, 25))
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
        load_validated_dataset(*paths, report_through=date(2026, 7, 25))


def test_report_through_cannot_precede_collection_start(tmp_path: Path) -> None:
    record = deepcopy(valid_record())
    record["published_at"] = "2026-07-20T09:00:00+05:30"
    paths = dataset_files(tmp_path, record)
    with pytest.raises(PublicDataValidationError, match="precedes collection_start"):
        load_validated_dataset(*paths, report_through=date(2026, 6, 30))
