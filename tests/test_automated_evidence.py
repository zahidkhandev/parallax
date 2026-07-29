from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.automated_evidence import build_record, extract_targets, generate
from src.inventory import (
    AvailabilityStatus,
    EligibilityStatus,
    MediaFormat,
    SourceInventoryRecord,
)
from src.models import (
    ActorType,
    EvidenceKind,
    EvidenceTier,
    ReviewStatus,
    StanceDirection,
)


def inventory_record(
    *,
    source_id: str = "src-test-record-001",
    title: str = "Students protest NTA over alleged NEET paper leak",
    language: str = "en",
) -> SourceInventoryRecord:
    timestamp = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    return SourceInventoryRecord(
        inventory_version="1.0.0",
        source_id=source_id,
        source_url=f"https://example.com/{source_id}",
        outlet="Example News",
        programme=None,
        title=title,
        published_at=timestamp,
        accessed_at=timestamp,
        original_language=language,
        media_format=MediaFormat.OTHER_NEWS_MEDIA,
        availability=AvailabilityStatus.AVAILABLE,
        eligibility=EligibilityStatus.INCLUDED,
        discovery_method="test",
        discovery_query=None,
        exclusion_reason=None,
        eligible_segment_start_seconds=None,
        eligible_segment_end_seconds=None,
        notes=None,
    )


def test_extracts_multiple_explicit_targets() -> None:
    targets = extract_targets("Students protest NTA over alleged NEET paper leak")
    pairs = {(target.name, target.actor_type) for target in targets}
    assert ("National Testing Agency (NTA)", ActorType.EDUCATION_EXAM_AUTHORITY) in pairs
    assert ("NEET candidates and students", ActorType.STUDENT_CANDIDATE) in pairs
    assert (
        "NEET protest organisers and participants",
        ActorType.PROTEST_ORGANISER,
    ) in pairs


def test_hindi_target_detection() -> None:
    targets = extract_targets("नीट छात्र एनटीए के खिलाफ प्रदर्शन करते हैं")
    actor_types = {target.actor_type for target in targets}
    assert ActorType.EDUCATION_EXAM_AUTHORITY in actor_types
    assert ActorType.STUDENT_CANDIDATE in actor_types
    assert ActorType.PROTEST_ORGANISER in actor_types


def test_build_record_is_conservative_machine_packaging() -> None:
    source = inventory_record(title="Police excesses alleged during NEET protest")
    police = next(
        target for target in extract_targets(source.title) if target.actor_type is ActorType.POLICE
    )
    record = build_record(source, police)
    assert record.evidence_kind is EvidenceKind.HEADLINE
    assert record.evidence_tier is EvidenceTier.C
    assert record.review_status is ReviewStatus.MACHINE_ONLY
    assert record.stance is StanceDirection.CRITICAL
    assert record.reviewer_ids == []
    assert record.reviewed_at is None
    assert record.packaging_support.value == "not_reviewed"


def test_generate_updates_jsonl_manifest_and_report(tmp_path: Path) -> None:
    inventory_path = tmp_path / "source-inventory.jsonl"
    data_path = tmp_path / "evidence-segments.jsonl"
    manifest_path = tmp_path / "collection-manifest.json"
    report_path = tmp_path / "report.json"

    source = inventory_record()
    inventory_path.write_text(
        f"{json.dumps(source.model_dump(mode='json'), sort_keys=True)}\n",
        encoding="utf-8",
    )
    data_path.write_text("", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "project": "Project Parallax",
                "repository": "neet-protest-2026-media-analysis",
                "dataset": "NEET Protest 2026 Media Analysis",
                "dataset_version": "0.1.0",
                "methodology_version": "1.0.0",
                "taxonomy_version": "1.0.0",
                "schema_version": "1.0.0",
                "status": "collection",
                "collection_start": "2026-07-01",
                "collection_end": None,
                "included_event": "NEET 2026 protests",
                "record_count": 0,
                "generated_at": None,
                "notes": "Rolling collection.",
            }
        ),
        encoding="utf-8",
    )

    report = generate(
        inventory_path=inventory_path,
        data_path=data_path,
        manifest_path=manifest_path,
        report_path=report_path,
        as_of=date(2026, 7, 29),
    )

    lines = data_path.read_text(encoding="utf-8").splitlines()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    written_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["generated_record_count"] == 3
    assert len(lines) == 3
    assert manifest["record_count"] == 3
    assert written_report["mode"] == "headline_packaging_metadata_only"
