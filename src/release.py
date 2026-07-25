"""Deterministic release-readiness assessment for validated public artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .analysis_models import AnalysisSummary
from .models import DatasetStatus, ReviewStatus
from .validate_public_data import ValidatedDataset


@dataclass(frozen=True)
class ReadinessCheck:
    check: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ReadinessReport:
    readiness_version: str
    ready: bool
    dataset_version: str
    report_through: str
    checks: tuple[ReadinessCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "readiness_version": self.readiness_version,
            "ready": self.ready,
            "dataset_version": self.dataset_version,
            "report_through": self.report_through,
            "checks": [asdict(check) for check in self.checks],
        }


def assess_release(dataset: ValidatedDataset, payload: dict[str, Any]) -> ReadinessReport:
    """Assess structural release criteria without making substantive research claims."""
    summary = AnalysisSummary.model_validate(payload)
    manifest = dataset.manifest
    machine_count = sum(
        record.review_status is ReviewStatus.MACHINE_ONLY for record in dataset.records
    )
    conflict_count = sum(summary.segment_annotation_conflict_counts.values())
    checks = (
        ReadinessCheck(
            "dataset_nonempty",
            bool(dataset.records),
            f"{len(dataset.records)} public evidence record(s)",
        ),
        ReadinessCheck(
            "collection_window_closed",
            manifest.collection_end is not None,
            "collection_end must be fixed for a versioned release",
        ),
        ReadinessCheck(
            "manifest_published",
            manifest.status is DatasetStatus.PUBLISHED,
            f"manifest status is {manifest.status.value}",
        ),
        ReadinessCheck(
            "release_timestamp_present",
            manifest.generated_at is not None,
            "generated_at is required for a versioned release",
        ),
        ReadinessCheck(
            "no_machine_only_records",
            machine_count == 0,
            f"{machine_count} machine-only record(s)",
        ),
        ReadinessCheck(
            "no_segment_annotation_conflicts",
            conflict_count == 0,
            f"{conflict_count} segment annotation conflict(s)",
        ),
        ReadinessCheck(
            "analysis_provenance_matches",
            summary.provenance is not None
            and summary.provenance.evidence_sha256 == dataset.evidence_sha256
            and summary.provenance.dataset_version == manifest.dataset_version
            and summary.provenance.report_through == dataset.report_through,
            "analysis must identify the validated evidence, dataset version, and report date",
        ),
    )
    return ReadinessReport(
        readiness_version="1.0.0",
        ready=all(check.passed for check in checks),
        dataset_version=manifest.dataset_version,
        report_through=dataset.report_through.isoformat(),
        checks=checks,
    )
