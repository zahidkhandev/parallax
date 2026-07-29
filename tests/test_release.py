from datetime import date

from src.analytics import AnalysisProvenance, build_summary
from src.models import CollectionManifest, EvidenceSegment
from src.release import assess_release
from src.validate_public_data import ValidatedDataset
from tests.test_manifest import manifest
from tests.test_models import valid_record


def make_dataset(*, published: bool) -> tuple[ValidatedDataset, dict]:
    record = EvidenceSegment.model_validate(valid_record())
    payload = manifest()
    payload.update(
        status="published" if published else "collection",
        record_count=1,
        collection_start="2026-05-01",
        collection_end="2026-05-31" if published else None,
        generated_at="2026-06-01T00:00:00Z" if published else None,
    )
    collection = CollectionManifest.model_validate(payload)
    dataset = ValidatedDataset(
        records=(record,),
        corrections=(),
        manifest=collection,
        evidence_sha256="a" * 64,
        report_through=date(2026, 5, 31),
        inventory=(),
    )
    summary = build_summary(
        dataset.records,
        provenance=AnalysisProvenance(
            dataset_version=collection.dataset_version,
            methodology_version=collection.methodology_version,
            taxonomy_version=collection.taxonomy_version,
            schema_version=collection.schema_version,
            evidence_sha256=dataset.evidence_sha256,
            correction_count=0,
            report_start="2026-05-01",
            report_through="2026-05-31",
            collection_end="2026-05-31" if published else None,
        ),
    )
    return dataset, summary


def test_structurally_complete_release_is_ready() -> None:
    dataset, summary = make_dataset(published=True)
    report = assess_release(dataset, summary)
    assert report.ready is True
    assert all(check.passed for check in report.checks)


def test_open_collection_is_not_mislabeled_as_release_ready() -> None:
    dataset, summary = make_dataset(published=False)
    report = assess_release(dataset, summary)
    failed = {check.check for check in report.checks if not check.passed}
    assert report.ready is False
    assert failed == {
        "collection_window_closed",
        "manifest_published",
        "release_timestamp_present",
    }


def test_provenance_mismatch_blocks_release() -> None:
    dataset, summary = make_dataset(published=True)
    summary["provenance"]["evidence_sha256"] = "b" * 64
    report = assess_release(dataset, summary)
    checks = {check.check: check.passed for check in report.checks}
    assert checks["analysis_provenance_matches"] is False
    assert report.ready is False
