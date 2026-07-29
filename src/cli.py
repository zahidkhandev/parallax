"""Command-line interface for validation, schema maintenance, and analysis."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from contextlib import suppress
from datetime import date
from pathlib import Path
from typing import Any

from .analysis_models import (
    DEFAULT_ANALYSIS_SCHEMA,
    canonical_analysis_schema,
    validate_analysis_schema_current,
)
from .analytics import AnalysisOptions, AnalysisProvenance, build_summary
from .inventory import (
    DEFAULT_INVENTORY,
    DEFAULT_INVENTORY_SCHEMA,
    build_inventory_audit,
    canonical_inventory_schema,
    read_inventory,
    validate_inventory_schema_current,
)
from .release import assess_release
from .reliability import (
    DEFAULT_RELIABILITY_DATA,
    DEFAULT_RELIABILITY_SCHEMA,
    build_reliability_report,
    canonical_reliability_schema,
    read_reliability_jsonl,
    validate_reliability_schema_current,
)
from .reporting import render_report
from .taxonomy import DEFAULT_TAXONOMY, canonical_taxonomy, validate_taxonomy_current
from .validate_public_data import (
    DEFAULT_CORRECTIONS,
    DEFAULT_DATA,
    DEFAULT_MANIFEST,
    DEFAULT_SCHEMA,
    PublicDataValidationError,
    ValidatedDataset,
    canonical_schema,
    load_validated_dataset,
    validate_public_data,
    validate_schema_current,
)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write formatted JSON without leaving a partial result on interruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


def _analysis_for_args(args: argparse.Namespace) -> tuple[ValidatedDataset, dict[str, Any]]:
    dataset = load_validated_dataset(
        args.data,
        args.schema,
        args.manifest,
        args.corrections,
        args.taxonomy,
        args.as_of,
        args.inventory,
        args.inventory_schema,
    )
    summary = build_summary(
        dataset.records,
        AnalysisOptions(args.include_machine_only, args.include_rejected),
        AnalysisProvenance(
            dataset_version=dataset.manifest.dataset_version,
            methodology_version=dataset.manifest.methodology_version,
            taxonomy_version=dataset.manifest.taxonomy_version,
            schema_version=dataset.manifest.schema_version,
            evidence_sha256=dataset.evidence_sha256,
            correction_count=len(dataset.corrections),
            report_start=dataset.manifest.collection_start.isoformat(),
            report_through=dataset.report_through.isoformat(),
            collection_end=(
                dataset.manifest.collection_end.isoformat()
                if dataset.manifest.collection_end
                else None
            ),
        ),
    )
    return dataset, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parallax")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate schema, JSONL, and manifest")
    validate.add_argument("--data", type=Path, default=DEFAULT_DATA)
    validate.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    validate.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    validate.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    validate.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    validate.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    validate.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    validate.add_argument("--inventory-schema", type=Path, default=DEFAULT_INVENTORY_SCHEMA)

    schema = subparsers.add_parser("schema", help="check or regenerate the JSON Schema")
    schema.add_argument("--path", type=Path, default=DEFAULT_SCHEMA)
    schema.add_argument("--write", action="store_true")

    taxonomy = subparsers.add_parser("taxonomy", help="check or regenerate the taxonomy")
    taxonomy.add_argument("--path", type=Path, default=DEFAULT_TAXONOMY)
    taxonomy.add_argument("--write", action="store_true")

    analysis_schema = subparsers.add_parser(
        "analysis-schema", help="check or regenerate the analysis JSON Schema"
    )
    analysis_schema.add_argument("--path", type=Path, default=DEFAULT_ANALYSIS_SCHEMA)
    analysis_schema.add_argument("--write", action="store_true")

    analyze = subparsers.add_parser("analyze", help="write transparent descriptive metrics")
    analyze.add_argument("--data", type=Path, default=DEFAULT_DATA)
    analyze.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    analyze.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    analyze.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    analyze.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    analyze.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--include-machine-only", action="store_true")
    analyze.add_argument("--include-rejected", action="store_true")
    analyze.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    analyze.add_argument("--inventory-schema", type=Path, default=DEFAULT_INVENTORY_SCHEMA)

    report = subparsers.add_parser("report", help="build a standalone accessible HTML report")
    report.add_argument("--data", type=Path, default=DEFAULT_DATA)
    report.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    report.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    report.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    report.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    report.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--metrics-output", type=Path)
    report.add_argument("--include-machine-only", action="store_true")
    report.add_argument("--include-rejected", action="store_true")
    report.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    report.add_argument("--inventory-schema", type=Path, default=DEFAULT_INVENTORY_SCHEMA)

    readiness = subparsers.add_parser(
        "readiness", help="assess structural acceptance criteria for a versioned release"
    )
    readiness.add_argument("--data", type=Path, default=DEFAULT_DATA)
    readiness.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    readiness.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    readiness.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    readiness.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    readiness.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    readiness.add_argument("--output", type=Path, required=True)
    readiness.add_argument("--include-machine-only", action="store_true")
    readiness.add_argument("--include-rejected", action="store_true")
    readiness.add_argument("--require-ready", action="store_true")
    readiness.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    readiness.add_argument("--inventory-schema", type=Path, default=DEFAULT_INVENTORY_SCHEMA)

    reliability = subparsers.add_parser(
        "reliability", help="calculate per-label agreement for double-coded records"
    )
    reliability.add_argument("--data", type=Path, default=DEFAULT_DATA)
    reliability.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    reliability.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    reliability.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    reliability.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    reliability.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    reliability.add_argument("--annotations", type=Path, default=DEFAULT_RELIABILITY_DATA)
    reliability.add_argument("--output", type=Path, required=True)
    reliability.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    reliability.add_argument("--inventory-schema", type=Path, default=DEFAULT_INVENTORY_SCHEMA)

    reliability_schema = subparsers.add_parser(
        "reliability-schema", help="check or regenerate the reliability JSON Schema"
    )
    reliability_schema.add_argument("--path", type=Path, default=DEFAULT_RELIABILITY_SCHEMA)
    reliability_schema.add_argument("--write", action="store_true")

    inventory_schema = subparsers.add_parser(
        "inventory-schema", help="check or regenerate the source inventory JSON Schema"
    )
    inventory_schema.add_argument("--path", type=Path, default=DEFAULT_INVENTORY_SCHEMA)
    inventory_schema.add_argument("--write", action="store_true")

    inventory_audit = subparsers.add_parser(
        "inventory-audit", help="summarize discovered-source collection coverage"
    )
    inventory_audit.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    inventory_audit.add_argument("--output", type=Path, required=True)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            report = validate_public_data(
                args.data,
                args.schema,
                args.manifest,
                args.corrections,
                args.taxonomy,
                args.as_of,
                args.inventory,
                args.inventory_schema,
            )
            print(
                f"Validated {report.record_count} record(s); "
                f"{report.reviewed_count} reviewed, {report.rejected_count} rejected, "
                f"{report.correction_count} correction(s)."
            )
        elif args.command == "schema":
            if args.write:
                write_json_atomic(args.path, canonical_schema())
                print(f"Wrote {args.path}.")
            else:
                validate_schema_current(args.path)
                print(f"Schema is current: {args.path}.")
        elif args.command == "taxonomy":
            if args.write:
                write_json_atomic(args.path, canonical_taxonomy())
                print(f"Wrote {args.path}.")
            else:
                try:
                    validate_taxonomy_current(args.path)
                except ValueError as exc:
                    raise PublicDataValidationError(str(exc)) from exc
                print(f"Taxonomy is current: {args.path}.")
        elif args.command == "analysis-schema":
            if args.write:
                write_json_atomic(args.path, canonical_analysis_schema())
                print(f"Wrote {args.path}.")
            else:
                try:
                    validate_analysis_schema_current(args.path)
                except ValueError as exc:
                    raise PublicDataValidationError(str(exc)) from exc
                print(f"Analysis schema is current: {args.path}.")
        elif args.command == "analyze":
            _, summary = _analysis_for_args(args)
            write_json_atomic(args.output, summary)
            print(f"Wrote {summary['population']['included_records']} record(s) to {args.output}.")
        elif args.command == "report":
            dataset, summary = _analysis_for_args(args)
            write_text_atomic(
                args.output, render_report(summary, dataset.records, dataset.corrections)
            )
            if args.metrics_output:
                write_json_atomic(args.metrics_output, summary)
            print(f"Wrote report through {args.as_of} to {args.output}.")
        elif args.command == "readiness":
            dataset, summary = _analysis_for_args(args)
            readiness = assess_release(dataset, summary)
            write_json_atomic(args.output, readiness.as_dict())
            state = "ready" if readiness.ready else "not ready"
            print(f"Release is {state}; wrote assessment to {args.output}.")
            if args.require_ready and not readiness.ready:
                return 2
        elif args.command == "reliability":
            dataset = load_validated_dataset(
                args.data,
                args.schema,
                args.manifest,
                args.corrections,
                args.taxonomy,
                args.as_of,
                args.inventory,
                args.inventory_schema,
            )
            annotations, errors = read_reliability_jsonl(
                args.annotations,
                known_record_ids={record.record_id for record in dataset.records},
            )
            if errors:
                raise PublicDataValidationError("\n".join(errors))
            report = build_reliability_report(annotations)
            write_json_atomic(args.output, report)
            print(
                f"Wrote reliability for {report['double_coded_pair_count']} pair(s) "
                f"to {args.output}."
            )
        elif args.command == "reliability-schema":
            if args.write:
                write_json_atomic(args.path, canonical_reliability_schema())
                print(f"Wrote {args.path}.")
            else:
                try:
                    validate_reliability_schema_current(args.path)
                except ValueError as exc:
                    raise PublicDataValidationError(str(exc)) from exc
                print(f"Reliability schema is current: {args.path}.")
        elif args.command == "inventory-schema":
            if args.write:
                write_json_atomic(args.path, canonical_inventory_schema())
                print(f"Wrote {args.path}.")
            else:
                try:
                    validate_inventory_schema_current(args.path)
                except ValueError as exc:
                    raise PublicDataValidationError(str(exc)) from exc
                print(f"Inventory schema is current: {args.path}.")
        elif args.command == "inventory-audit":
            inventory, errors = read_inventory(args.inventory)
            if errors:
                raise PublicDataValidationError("\n".join(errors))
            audit = build_inventory_audit(inventory)
            write_json_atomic(args.output, audit)
            print(f"Wrote inventory audit for {len(inventory)} source(s) to {args.output}.")
    except (OSError, PublicDataValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    raise SystemExit(run())
