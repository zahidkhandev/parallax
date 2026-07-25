import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.models import CollectionManifest
from src.validate_public_data import PublicDataValidationError, validate_manifest


def manifest() -> dict:
    return {
        "project": "Project Parallax",
        "repository": "neet-protest-2026-media-analysis",
        "dataset": "NEET Protest 2026 Media Analysis",
        "dataset_version": "0.1.0",
        "methodology_version": "1.0.0",
        "taxonomy_version": "1.0.0",
        "schema_version": "1.0.0",
        "status": "scaffold_no_observations",
        "collection_start": None,
        "collection_end": None,
        "included_event": "NEET 2026 protests",
        "record_count": 0,
        "generated_at": None,
        "notes": "Test manifest.",
    }


def test_valid_scaffold_manifest() -> None:
    assert CollectionManifest.model_validate(manifest()).record_count == 0


def test_collection_window_can_be_open_but_end_requires_start() -> None:
    payload = manifest()
    payload["collection_start"] = "2026-06-02"
    assert CollectionManifest.model_validate(payload).collection_end is None
    payload["collection_start"] = None
    payload["collection_end"] = "2026-06-03"
    with pytest.raises(ValidationError, match="requires collection_start"):
        CollectionManifest.model_validate(payload)
    payload["collection_start"] = "2026-06-02"
    payload["collection_end"] = "2026-06-01"
    with pytest.raises(ValidationError, match="must not precede"):
        CollectionManifest.model_validate(payload)


def test_published_manifest_requires_release_metadata() -> None:
    payload = manifest()
    payload["status"] = "published"
    with pytest.raises(ValidationError, match="closed collection window"):
        CollectionManifest.model_validate(payload)


def test_nonempty_public_data_requires_collection_dates(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    payload = manifest()
    payload.update(status="review", record_count=1)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PublicDataValidationError, match="collection dates"):
        validate_manifest(path, actual_record_count=1)
