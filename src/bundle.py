"""Deterministic, public-only release bundle construction."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

from .analytics import AnalysisOptions, AnalysisProvenance, build_summary
from .inventory import build_inventory_audit
from .release import assess_release
from .reliability import build_reliability_report, read_reliability_jsonl
from .reporting import render_report
from .validate_public_data import ValidatedDataset

PUBLIC_DOCS = (
    "README.md",
    "SCOPE.md",
    "METHODOLOGY.md",
    "COLLECTION_PROTOCOL.md",
    "REVIEWER_HANDBOOK.md",
    "CORRECTIONS.md",
    "RELEASE.md",
    "DATA_LICENSE.md",
    "NOTICE.md",
    "LICENSE",
)
CONTRACT_FILES = (
    "schemas/evidence-segment.schema.json",
    "schemas/analysis-summary.schema.json",
    "schemas/reliability-annotation.schema.json",
    "schemas/source-inventory.schema.json",
    "methodology/taxonomy.json",
)


class BundleBuildError(ValueError):
    """Raised when public bundle inputs cannot be safely assembled."""


class BundleNotReadyError(BundleBuildError):
    """Raised when a strict bundle is requested before readiness checks pass."""


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def build_release_bundle(
    *,
    root: Path,
    output: Path,
    dataset: ValidatedDataset,
    manifest_path: Path,
    evidence_path: Path,
    inventory_path: Path,
    corrections_path: Path,
    reliability_path: Path,
    draft: bool,
) -> dict[str, Any]:
    options = AnalysisOptions()
    manifest = dataset.manifest
    summary = build_summary(
        dataset.records,
        options,
        AnalysisProvenance(
            dataset_version=manifest.dataset_version,
            methodology_version=manifest.methodology_version,
            taxonomy_version=manifest.taxonomy_version,
            schema_version=manifest.schema_version,
            evidence_sha256=dataset.evidence_sha256,
            correction_count=len(dataset.corrections),
            report_start=manifest.collection_start.isoformat(),
            report_through=dataset.report_through.isoformat(),
            collection_end=manifest.collection_end.isoformat() if manifest.collection_end else None,
        ),
    )
    readiness = assess_release(dataset, summary)
    if not draft and not readiness.ready:
        failed = ", ".join(check.check for check in readiness.checks if not check.passed)
        raise BundleNotReadyError(f"release is not ready: {failed}")
    annotations, errors = read_reliability_jsonl(
        reliability_path,
        known_record_ids={record.record_id for record in dataset.records},
    )
    if errors:
        raise BundleBuildError("\n".join(errors))
    reliability = build_reliability_report(annotations)
    inventory_audit = build_inventory_audit(list(dataset.inventory))

    output_parent = output.parent.resolve()
    output_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output_parent))
    backup = output.with_name(f".{output.name}.backup")
    try:
        data_dir = stage / "public-data"
        data_dir.mkdir()
        for source, name in (
            (evidence_path, "evidence-segments.jsonl"),
            (inventory_path, "source-inventory.jsonl"),
            (corrections_path, "corrections.csv"),
            (reliability_path, "reliability-annotations.jsonl"),
        ):
            shutil.copyfile(source, data_dir / name)
        shutil.copyfile(
            manifest_path,
            data_dir / "collection-manifest.json",
        )

        for relative in CONTRACT_FILES:
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, destination)
        docs = stage / "docs"
        docs.mkdir()
        for relative in PUBLIC_DOCS:
            shutil.copyfile(root / relative, docs / relative)

        artifacts = stage / "artifacts"
        artifacts.mkdir()
        _write_json(artifacts / "metrics.json", summary)
        (artifacts / "report.html").write_text(
            render_report(summary, dataset.records, dataset.corrections), encoding="utf-8"
        )
        _write_json(artifacts / "readiness.json", readiness.as_dict())
        _write_json(artifacts / "reliability.json", reliability)
        _write_json(artifacts / "inventory-audit.json", inventory_audit)

        files = sorted(
            path.relative_to(stage).as_posix()
            for path in stage.rglob("*")
            if path.is_file()
        )
        checksums = {relative: _digest(stage / relative) for relative in files}
        bundle_manifest = {
            "bundle_version": "1.0.0",
            "dataset_version": manifest.dataset_version,
            "report_start": manifest.collection_start.isoformat(),
            "report_through": dataset.report_through.isoformat(),
            "draft": draft,
            "ready": readiness.ready,
            "artifact_count": len(files),
            "sha256": checksums,
        }
        _write_json(stage / "bundle-manifest.json", bundle_manifest)
        (stage / "SHA256SUMS").write_text(
            "".join(f"{digest}  {relative}\n" for relative, digest in checksums.items()),
            encoding="utf-8",
        )

        if backup.exists():
            shutil.rmtree(backup)
        if output.exists():
            os.replace(output, backup)
        os.replace(stage, output)
        if backup.exists():
            shutil.rmtree(backup)
        return bundle_manifest
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        if backup.exists() and not output.exists():
            os.replace(backup, output)
        raise
