import csv
from pathlib import Path

from src.validate_public_data import CORRECTION_COLUMNS, read_corrections


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CORRECTION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def valid_correction() -> dict[str, str]:
    return {
        "correction_id": "cor-example-001",
        "record_id": "test-segment-001",
        "corrected_at": "2026-05-04T10:00:00Z",
        "field": "target_actor.name",
        "original_value": "Old target",
        "corrected_value": "Corrected target",
        "reason": "The source identifies the corrected target.",
        "reviewer": "reviewer-002",
        "metrics_affected": "true",
    }


def test_correction_log_accepts_valid_referenced_record(tmp_path: Path) -> None:
    path = tmp_path / "corrections.csv"
    write_rows(path, [valid_correction()])
    corrections, errors = read_corrections(path, known_record_ids={"test-segment-001"})
    assert not errors
    assert corrections[0].metrics_affected is True


def test_correction_log_rejects_unknown_record_and_duplicate_id(tmp_path: Path) -> None:
    path = tmp_path / "corrections.csv"
    row = valid_correction()
    unknown = {
        **row,
        "correction_id": "cor-example-002",
        "record_id": "missing-record",
    }
    duplicate = {**row, "corrected_value": "Another target"}
    write_rows(path, [row, unknown, duplicate])
    corrections, errors = read_corrections(path, known_record_ids={"test-segment-001"})
    assert len(corrections) == 1
    assert any("is not in public evidence" in error for error in errors)
    assert any("duplicate correction_id" in error for error in errors)


def test_correction_log_rejects_changed_header(tmp_path: Path) -> None:
    path = tmp_path / "corrections.csv"
    path.write_text("record_id,correction_id\n", encoding="utf-8")
    corrections, errors = read_corrections(path, known_record_ids=set())
    assert not corrections
    assert errors == [
        f"{path}: header must be exactly {','.join(CORRECTION_COLUMNS)}"
    ]


def test_correction_log_rejects_unknown_model_field(tmp_path: Path) -> None:
    path = tmp_path / "corrections.csv"
    row = valid_correction()
    row["field"] = "target_actor.typo"
    write_rows(path, [row])
    corrections, errors = read_corrections(path, known_record_ids={"test-segment-001"})
    assert not corrections
    assert any("not an evidence-model path" in error for error in errors)


def test_correction_log_rejects_no_op_and_ambiguous_boolean(tmp_path: Path) -> None:
    path = tmp_path / "corrections.csv"
    no_op = valid_correction()
    no_op["corrected_value"] = no_op["original_value"]
    ambiguous = valid_correction()
    ambiguous["correction_id"] = "cor-example-002"
    ambiguous["metrics_affected"] = "yes"
    write_rows(path, [no_op, ambiguous])
    corrections, errors = read_corrections(path, known_record_ids={"test-segment-001"})
    assert not corrections
    assert any("must be 'true' or 'false'" in error for error in errors)
    assert any("must differ" in error for error in errors)
