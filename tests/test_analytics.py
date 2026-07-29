from copy import deepcopy

from src.analytics import AnalysisOptions, build_summary
from src.models import EvidenceSegment
from tests.test_models import valid_record


def record(**changes: object) -> EvidenceSegment:
    payload = deepcopy(valid_record())
    for key, value in changes.items():
        payload[key] = value
    return EvidenceSegment.model_validate(payload)


def test_summary_separates_targets_speakers_sources_and_dimensions() -> None:
    first = record()
    payload = deepcopy(valid_record())
    payload.update(
        record_id="test-segment-002",
        stance="critical",
        claim_type="reported_allegation",
        allegation_qualified=True,
        certainty="explicitly_qualified",
        segment_start_seconds=20.0,
        segment_end_seconds=30.0,
        topic_labels=["protest_demands", "examination_administration"],
        attributed_sources=["Student statement"],
        loaded_language=[{"term": "dramatic", "rationale": "Synthetic test rationale."}],
    )
    payload["target_actor"] = {"name": "Test organiser", "actor_type": "protest_organiser"}
    payload["speaker"] = {"name": "Test anchor", "role": "anchor"}
    second = EvidenceSegment.model_validate(payload)
    duplicate_segment_payload = deepcopy(payload)
    duplicate_segment_payload["record_id"] = "test-segment-003"
    duplicate_segment_payload["target_actor"] = {
        "name": "Test students",
        "actor_type": "student_candidate",
    }
    duplicate_segment_payload["stance"] = "favourable"
    third = EvidenceSegment.model_validate(duplicate_segment_payload)

    summary = build_summary([first, second, third])

    assert summary["population"]["included_records"] == 3
    assert summary["population"]["included_distinct_segments"] == 2
    assert summary["population"]["additional_target_records"] == 1
    assert summary["stance_by_target_actor"]["Test authority"] == {"neutral_descriptive": 1}
    assert summary["stance_by_target_actor"]["Test organiser"] == {"critical": 1}
    assert summary["stance_by_target_actor"]["Test students"] == {"favourable": 1}
    assert summary["speaker_role_counts"] == {"anchor": 1, "guest": 1}
    assert summary["attributed_source_counts"] == {
        "Student statement": 1,
        "Test document": 1,
    }
    assert summary["topic_record_counts"]["examination_administration"] == 2
    assert summary["topic_duration_seconds"]["examination_administration"] == 20.0
    assert summary["topic_duration_seconds"]["protest_demands"] == 10.0
    assert summary["frame_segment_counts"] == {"procedural_legal": 2}
    assert summary["frame_duration_seconds"] == {"procedural_legal": 20.0}
    assert summary["speaker_role_duration_seconds"] == {"anchor": 10.0, "guest": 10.0}
    assert summary["population"]["included_spoken_duration_seconds"] == 20.0
    assert summary["outlet_record_counts"] == {"Test outlet": 3}
    assert summary["outlet_segment_counts"] == {"Test outlet": 2}
    assert summary["stance_by_outlet_and_target_type"]["Test outlet"] == {
        "education_exam_authority": {"neutral_descriptive": 1},
        "protest_organiser": {"critical": 1},
        "student_candidate": {"favourable": 1},
    }
    assert summary["allegation_qualification_counts"]["qualified"] == 1
    assert summary["allegation_qualification_counts"]["total_allegations"] == 1
    assert summary["evidence_tier_counts"] == {"A": 3}
    assert summary["evidence_tier_segment_counts"] == {"A": 2}
    assert summary["segment_annotation_conflict_counts"] == {}
    assert "universal bias score" in summary["notes"][2]
    assert "non-exclusive" in summary["notes"][3]
    assert "deduplicate" in summary["notes"][4]


def test_machine_and_rejected_records_are_excluded_by_default() -> None:
    machine_payload = deepcopy(valid_record())
    machine_payload.update(
        record_id="test-machine-001",
        review_status="machine_only",
        reviewed_at=None,
        reviewer_ids=[],
    )
    rejected_payload = deepcopy(valid_record())
    rejected_payload.update(record_id="test-rejected-001", review_status="rejected")
    records = [
        EvidenceSegment.model_validate(machine_payload),
        EvidenceSegment.model_validate(rejected_payload),
    ]

    default = build_summary(records)
    assert default["population"]["included_records"] == 0
    assert default["population"]["human_review_coverage"] == 0.5

    rejected_only = build_summary(records, AnalysisOptions(include_rejected=True))
    assert rejected_only["population"]["included_records"] == 1

    machine_only = build_summary(records, AnalysisOptions(include_machine_only=True))
    assert machine_only["population"]["included_records"] == 1

    expanded = build_summary(records, AnalysisOptions(True, True))
    assert expanded["population"]["included_records"] == 2


def test_segment_annotation_conflicts_are_visible() -> None:
    first_payload = deepcopy(valid_record())
    first_payload.update(
        evidence_kind="headline",
        evidence_tier="C",
        packaging_support="partially_supported",
    )
    second_payload = deepcopy(first_payload)
    second_payload["record_id"] = "test-packaging-002"
    second_payload["packaging_support"] = "supported_by_body"

    summary = build_summary(
        [
            EvidenceSegment.model_validate(first_payload),
            EvidenceSegment.model_validate(second_payload),
        ]
    )

    assert summary["population"]["included_records"] == 2
    assert summary["population"]["included_distinct_segments"] == 1
    assert summary["packaging_support_counts"] == {"conflicting_annotations": 1}
    assert summary["segment_annotation_conflict_counts"] == {"packaging_support": 1}
