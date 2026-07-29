"""Validation services for Project Parallax public data."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from .inventory import (
    DEFAULT_INVENTORY,
    DEFAULT_INVENTORY_SCHEMA,
    EligibilityStatus,
    SourceInventoryRecord,
    read_inventory,
    validate_inventory_schema_current,
)
from .models import CollectionManifest, CorrectionRecord, EvidenceSegment
from .taxonomy import DEFAULT_TAXONOMY, canonical_taxonomy, validate_taxonomy_current

DEFAULT_DATA = Path("public-data/evidence-segments.jsonl")
DEFAULT_MANIFEST = Path("public-data/collection-manifest.json")
DEFAULT_SCHEMA = Path("schemas/evidence-segment.schema.json")
DEFAULT_CORRECTIONS = Path("public-data/corrections.csv")
CORRECTION_COLUMNS = tuple(CorrectionRecord.model_fields)


class PublicDataValidationError(ValueError):
    """Raised after all detectable public-data errors have been collected."""


@dataclass(frozen=True)
class ValidationReport:
    record_count: int
    reviewed_count: int
    rejected_count: int
    correction_count: int


@dataclass(frozen=True)
class ValidatedDataset:
    records: tuple[EvidenceSegment, ...]
    corrections: tuple[CorrectionRecord, ...]
    manifest: CollectionManifest
    evidence_sha256: str
    report_through: date
    inventory: tuple[SourceInventoryRecord, ...]


def canonical_schema() -> dict[str, Any]:
    """Return the canonical public schema generated from the Pydantic model."""
    schema = EvidenceSegment.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://project-parallax.example/schemas/evidence-segment.schema.json"
    return schema


def load_schema(path: Path) -> dict[str, Any]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicDataValidationError(f"Cannot load schema {path}: {exc}") from exc
    Draft202012Validator.check_schema(schema)
    return schema


def validate_schema_current(schema_path: Path = DEFAULT_SCHEMA) -> None:
    """Fail when the checked-in JSON Schema has drifted from the Pydantic model."""
    checked_in = load_schema(schema_path)
    if checked_in != canonical_schema():
        raise PublicDataValidationError(
            f"{schema_path} is out of date; run 'parallax schema --write'"
        )


def read_jsonl(
    path: Path, schema_path: Path = DEFAULT_SCHEMA
) -> tuple[list[EvidenceSegment], list[str]]:
    schema = load_schema(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    records: list[EvidenceSegment] = []
    errors: list[str] = []
    record_ids: set[str] = set()

    try:
        handle = path.open(encoding="utf-8")
    except OSError as exc:
        return records, [f"Cannot read {path}: {exc}"]

    with handle:
        for line_number, raw_line in enumerate(handle, start=1):
            location = f"{path}:{line_number}"
            if not raw_line.strip():
                errors.append(f"{location}: blank lines are not valid JSONL records")
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                errors.append(f"{location}: invalid JSON: {exc.msg}")
                continue

            schema_errors = sorted(
                validator.iter_errors(payload), key=lambda item: [str(part) for part in item.path]
            )
            errors.extend(f"{location}: schema: {error.message}" for error in schema_errors)
            try:
                model = EvidenceSegment.model_validate(payload)
            except ValidationError as exc:
                errors.append(f"{location}: model: {exc}")
                continue
            if model.record_id in record_ids:
                errors.append(f"{location}: duplicate record_id {model.record_id!r}")
                continue
            record_ids.add(model.record_id)
            records.append(model)
    return records, errors


def validate_manifest(path: Path, *, actual_record_count: int) -> CollectionManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = CollectionManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PublicDataValidationError(f"Invalid manifest {path}: {exc}") from exc
    if manifest.record_count != actual_record_count:
        raise PublicDataValidationError(
            f"{path}: record_count is {manifest.record_count}, expected {actual_record_count}"
        )
    if actual_record_count and manifest.collection_start is None:
        raise PublicDataValidationError(
            f"{path}: collection dates are required when evidence records exist"
        )
    return manifest


def is_correction_field(field: str) -> bool:
    parts = field.split(".")
    if parts[0] not in EvidenceSegment.model_fields:
        return False
    if len(parts) == 1:
        return True
    nested_fields = {
        "speaker": {"name", "role", "affiliation", "represented_actor_type"},
        "target_actor": {"name", "actor_type"},
    }
    return len(parts) == 2 and parts[1] in nested_fields.get(parts[0], set())


def read_corrections(
    path: Path, *, known_record_ids: set[str]
) -> tuple[list[CorrectionRecord], list[str]]:
    corrections: list[CorrectionRecord] = []
    errors: list[str] = []
    correction_ids: set[str] = set()
    try:
        handle = path.open(encoding="utf-8", newline="")
    except OSError as exc:
        return corrections, [f"Cannot read {path}: {exc}"]

    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return corrections, [f"{path}: missing CSV header"]
        if tuple(reader.fieldnames) != CORRECTION_COLUMNS:
            return corrections, [
                f"{path}: header must be exactly {','.join(CORRECTION_COLUMNS)}"
            ]
        for line_number, row in enumerate(reader, start=2):
            location = f"{path}:{line_number}"
            try:
                correction = CorrectionRecord.model_validate(row)
            except ValidationError as exc:
                errors.append(f"{location}: {exc}")
                continue
            if correction.correction_id in correction_ids:
                errors.append(f"{location}: duplicate correction_id {correction.correction_id!r}")
                continue
            correction_ids.add(correction.correction_id)
            if not is_correction_field(correction.field):
                errors.append(
                    f"{location}: field {correction.field!r} is not an evidence-model path"
                )
                continue
            if correction.record_id not in known_record_ids:
                errors.append(
                    f"{location}: record_id {correction.record_id!r} is not in public evidence"
                )
                continue
            corrections.append(correction)
    return corrections, errors


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_validated_dataset(
    data_path: Path = DEFAULT_DATA,
    schema_path: Path = DEFAULT_SCHEMA,
    manifest_path: Path = DEFAULT_MANIFEST,
    corrections_path: Path = DEFAULT_CORRECTIONS,
    taxonomy_path: Path = DEFAULT_TAXONOMY,
    report_through: date | None = None,
    inventory_path: Path = DEFAULT_INVENTORY,
    inventory_schema_path: Path = DEFAULT_INVENTORY_SCHEMA,
    *,
    check_schema_drift: bool = True,
) -> ValidatedDataset:
    if check_schema_drift:
        validate_schema_current(schema_path)
    try:
        validate_taxonomy_current(taxonomy_path)
    except ValueError as exc:
        raise PublicDataValidationError(str(exc)) from exc
    try:
        validate_inventory_schema_current(inventory_schema_path)
    except ValueError as exc:
        raise PublicDataValidationError(str(exc)) from exc
    report_through = report_through or date.today()
    records, errors = read_jsonl(data_path, schema_path)
    if errors:
        raise PublicDataValidationError("\n".join(errors))
    manifest = validate_manifest(manifest_path, actual_record_count=len(records))
    if manifest.collection_start is None:
        raise PublicDataValidationError(f"{manifest_path}: collection_start is required")
    if report_through < manifest.collection_start:
        raise PublicDataValidationError(
            f"report-through date {report_through} precedes collection_start"
        )
    if manifest.collection_end is not None and report_through > manifest.collection_end:
        raise PublicDataValidationError(
            f"report-through date {report_through} exceeds collection_end"
        )
    inventory, inventory_errors = read_inventory(inventory_path)
    if inventory_errors:
        raise PublicDataValidationError("\n".join(inventory_errors))
    included_inventory_urls = {
        str(item.source_url)
        for item in inventory
        if item.eligibility is EligibilityStatus.INCLUDED
    }
    for record in records:
        if record.published_at is None:
            raise PublicDataValidationError(
                f"record {record.record_id!r}: published_at is required for window validation"
            )
        published_date = record.published_at.date()
        if not manifest.collection_start <= published_date <= report_through:
            raise PublicDataValidationError(
                f"record {record.record_id!r}: publication date {published_date} is outside "
                f"{manifest.collection_start} through {report_through}"
            )
        if str(record.source_url) not in included_inventory_urls:
            raise PublicDataValidationError(
                f"record {record.record_id!r}: source_url is not an included inventory source"
            )
    for item in inventory:
        if item.eligibility is not EligibilityStatus.INCLUDED or item.published_at is None:
            continue
        published_date = item.published_at.date()
        if not manifest.collection_start <= published_date <= report_through:
            raise PublicDataValidationError(
                f"inventory source {item.source_id!r}: publication date {published_date} is "
                f"outside {manifest.collection_start} through {report_through}"
            )
    if manifest.taxonomy_version != canonical_taxonomy()["version"]:
        raise PublicDataValidationError(
            f"{manifest_path}: taxonomy_version does not match the controlled taxonomy"
        )
    schema_versions = {record.schema_version for record in records}
    if schema_versions and schema_versions != {manifest.schema_version}:
        raise PublicDataValidationError(
            f"{manifest_path}: schema_version does not match all evidence records"
        )
    corrections, correction_errors = read_corrections(
        corrections_path, known_record_ids={record.record_id for record in records}
    )
    if correction_errors:
        raise PublicDataValidationError("\n".join(correction_errors))
    try:
        evidence_digest = file_sha256(data_path)
    except OSError as exc:
        raise PublicDataValidationError(f"Cannot hash {data_path}: {exc}") from exc
    return ValidatedDataset(
        records=tuple(records),
        corrections=tuple(corrections),
        manifest=manifest,
        evidence_sha256=evidence_digest,
        report_through=report_through,
        inventory=tuple(inventory),
    )


def validate_public_data(
    data_path: Path = DEFAULT_DATA,
    schema_path: Path = DEFAULT_SCHEMA,
    manifest_path: Path = DEFAULT_MANIFEST,
    corrections_path: Path = DEFAULT_CORRECTIONS,
    taxonomy_path: Path = DEFAULT_TAXONOMY,
    report_through: date | None = None,
    inventory_path: Path = DEFAULT_INVENTORY,
    inventory_schema_path: Path = DEFAULT_INVENTORY_SCHEMA,
    *,
    check_schema_drift: bool = True,
) -> ValidationReport:
    dataset = load_validated_dataset(
        data_path,
        schema_path,
        manifest_path,
        corrections_path,
        taxonomy_path,
        report_through,
        inventory_path,
        inventory_schema_path,
        check_schema_drift=check_schema_drift,
    )
    return ValidationReport(
        record_count=len(dataset.records),
        reviewed_count=sum(
            record.review_status.value != "machine_only" for record in dataset.records
        ),
        rejected_count=sum(
            record.review_status.value == "rejected" for record in dataset.records
        ),
        correction_count=len(dataset.corrections),
    )


# Kept as a stable library API for integrations created from the initial scaffold.
def validate_jsonl(path: Path, schema_path: Path = DEFAULT_SCHEMA) -> int:
    records, errors = read_jsonl(path, schema_path)
    if errors:
        raise PublicDataValidationError("\n".join(errors))
    return len(records)


def main() -> None:
    """Compatibility entry point; the full CLI lives in :mod:`src.cli`."""
    try:
        report = validate_public_data()
    except PublicDataValidationError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Validated {report.record_count} public evidence record(s) in {DEFAULT_DATA}.")


if __name__ == "__main__":
    main()
