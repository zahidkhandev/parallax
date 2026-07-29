import json
from pathlib import Path

import pytest

from src.models import EvidenceSegment
from src.validate_public_data import validate_jsonl
from tests.test_models import valid_record


def write_schema(path: Path) -> None:
    path.write_text(json.dumps(EvidenceSegment.model_json_schema()), encoding="utf-8")


def test_validator_accepts_jsonl(tmp_path: Path) -> None:
    data = tmp_path / "evidence.jsonl"
    schema = tmp_path / "schema.json"
    data.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
    write_schema(schema)
    assert validate_jsonl(data, schema) == 1


def test_validator_rejects_duplicate_ids(tmp_path: Path) -> None:
    data = tmp_path / "evidence.jsonl"
    schema = tmp_path / "schema.json"
    line = json.dumps(valid_record()) + "\n"
    data.write_text(line + line, encoding="utf-8")
    write_schema(schema)
    with pytest.raises(ValueError, match="duplicate record_id"):
        validate_jsonl(data, schema)


def test_validator_rejects_blank_lines(tmp_path: Path) -> None:
    data = tmp_path / "evidence.jsonl"
    schema = tmp_path / "schema.json"
    data.write_text("\n", encoding="utf-8")
    write_schema(schema)
    with pytest.raises(ValueError, match="blank lines"):
        validate_jsonl(data, schema)
