import json
from pathlib import Path

import pytest

from src.taxonomy import canonical_taxonomy, load_taxonomy, validate_taxonomy_current


def test_canonical_taxonomy_contains_event_and_controlled_labels() -> None:
    taxonomy = canonical_taxonomy()
    assert taxonomy["event_scope"] == "NEET 2026 protests"
    assert "protest_demands" in taxonomy["topic_labels"]
    assert "procedural_legal" in taxonomy["frame_labels"]
    assert taxonomy["evidence_tiers"]["A"].startswith("timestamped spoken evidence")


def test_taxonomy_drift_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "taxonomy.json"
    payload = canonical_taxonomy()
    payload["topic_labels"].append("uncontrolled")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="out of date"):
        validate_taxonomy_current(path)


def test_non_object_taxonomy_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "taxonomy.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_taxonomy(path)
