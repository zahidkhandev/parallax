import json
from pathlib import Path

from src.cli import run
from src.inventory import canonical_inventory_schema
from src.validate_public_data import canonical_schema
from tests.test_corrections import valid_correction, write_rows
from tests.test_manifest import manifest
from tests.test_models import valid_record


def test_validate_and_analyze_commands(tmp_path: Path) -> None:
    data = tmp_path / "evidence.jsonl"
    schema = tmp_path / "schema.json"
    manifest_path = tmp_path / "manifest.json"
    corrections = tmp_path / "corrections.csv"
    output = tmp_path / "metrics.json"
    report = tmp_path / "report.html"
    readiness = tmp_path / "readiness.json"
    inventory = tmp_path / "inventory.jsonl"
    inventory_schema = tmp_path / "inventory-schema.json"
    data.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
    schema.write_text(json.dumps(canonical_schema()), encoding="utf-8")
    payload = manifest()
    payload.update(
        status="review",
        record_count=1,
        collection_start="2026-05-01",
        collection_end="2026-05-31",
    )
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    write_rows(corrections, [valid_correction()])
    inventory.write_text(
        json.dumps(
            {
                "inventory_version": "1.0.0",
                "source_id": "src-test-001",
                "source_url": valid_record()["source_url"],
                "outlet": "Test outlet",
                "programme": "Test programme",
                "title": "Synthetic test source",
                "published_at": "2026-05-01T09:00:00+05:30",
                "accessed_at": "2026-05-02T10:00:00Z",
                "original_language": "en",
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
        )
        + "\n",
        encoding="utf-8",
    )
    inventory_schema.write_text(json.dumps(canonical_inventory_schema()), encoding="utf-8")

    common = [
        "--data",
        str(data),
        "--schema",
        str(schema),
        "--manifest",
        str(manifest_path),
        "--corrections",
        str(corrections),
        "--as-of",
        "2026-05-31",
        "--inventory",
        str(inventory),
        "--inventory-schema",
        str(inventory_schema),
    ]
    # A custom schema is structurally valid but drift checking still compares canonical content.
    assert run(["validate", *common]) == 0
    assert run(["analyze", *common, "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["population"]["included_records"] == 1
    assert result["provenance"]["dataset_version"] == "0.1.0"
    assert len(result["provenance"]["evidence_sha256"]) == 64
    assert result["provenance"]["correction_count"] == 1
    assert result["provenance"]["report_start"] == "2026-05-01"
    assert result["provenance"]["report_through"] == "2026-05-31"
    assert run(["report", *common, "--output", str(report)]) == 0
    html = report.read_text(encoding="utf-8")
    assert "01 May 2026 through 31 May 2026" in html
    assert "Targeted stance" in html
    assert run(["readiness", *common, "--output", str(readiness)]) == 0
    assert json.loads(readiness.read_text())["ready"] is False
    assert (
        run(["readiness", *common, "--output", str(readiness), "--require-ready"])
        == 2
    )


def test_validate_reports_manifest_count_mismatch(tmp_path: Path, capsys: object) -> None:
    data = tmp_path / "evidence.jsonl"
    schema = tmp_path / "schema.json"
    manifest_path = tmp_path / "manifest.json"
    data.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
    schema.write_text(json.dumps(canonical_schema()), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")

    result = run(
        [
            "validate",
            "--data",
            str(data),
            "--schema",
            str(schema),
            "--manifest",
            str(manifest_path),
        ]
    )
    assert result == 1
    assert "record_count" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_schema_command_detects_drift(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text("{}", encoding="utf-8")
    assert run(["schema", "--path", str(schema)]) == 1
    assert run(["schema", "--path", str(schema), "--write"]) == 0
    assert run(["schema", "--path", str(schema)]) == 0


def test_taxonomy_command_detects_drift(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_text("{}", encoding="utf-8")
    assert run(["taxonomy", "--path", str(taxonomy)]) == 1
    assert run(["taxonomy", "--path", str(taxonomy), "--write"]) == 0
    assert run(["taxonomy", "--path", str(taxonomy)]) == 0


def test_analysis_schema_command_detects_drift(tmp_path: Path) -> None:
    schema = tmp_path / "analysis-schema.json"
    schema.write_text("{}", encoding="utf-8")
    assert run(["analysis-schema", "--path", str(schema)]) == 1
    assert run(["analysis-schema", "--path", str(schema), "--write"]) == 0
    assert run(["analysis-schema", "--path", str(schema)]) == 0
