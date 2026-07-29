import json
from copy import deepcopy
from pathlib import Path

from src.reliability import (
    ReliabilityAnnotation,
    build_reliability_report,
    canonical_reliability_schema,
    read_reliability_jsonl,
    validate_reliability_schema_current,
)


def annotation(record_id: str, reviewer: str, **changes: object) -> ReliabilityAnnotation:
    payload = {
        "annotation_version": "1.0.0",
        "record_id": record_id,
        "reviewer_id": reviewer,
        "round_id": "pilot-001",
        "target_actor_name": "Test authority",
        "target_actor_type": "education_exam_authority",
        "speaker_role": "guest",
        "stance": "neutral_descriptive",
        "claim_type": "observed_fact",
        "certainty": "explicitly_qualified",
        "evidence_tier": "A",
        "topic_labels": ["examination_administration"],
        "frame_labels": ["procedural_legal"],
    }
    payload.update(changes)
    return ReliabilityAnnotation.model_validate(payload)


def test_reliability_reports_each_label_separately() -> None:
    annotations = [
        annotation("record-001", "reviewer-001", stance="favourable"),
        annotation("record-001", "reviewer-002", stance="favourable"),
        annotation("record-002", "reviewer-001", stance="critical"),
        annotation(
            "record-002",
            "reviewer-002",
            stance="favourable",
            topic_labels=["protest_demands"],
        ),
    ]
    report = build_reliability_report(annotations)
    assert report["double_coded_pair_count"] == 2
    assert report["metrics"]["stance"] == {
        "pair_count": 2,
        "percent_agreement": 0.5,
        "cohen_kappa": 0.0,
    }
    assert report["metrics"]["topic_labels"]["exact_agreement"] == 0.5
    assert report["metrics"]["topic_labels"]["mean_jaccard"] == 0.5
    assert "not combined" in report["notes"][0]


def test_groups_without_exactly_two_reviewers_are_excluded() -> None:
    report = build_reliability_report([annotation("record-001", "reviewer-001")])
    assert report["double_coded_pair_count"] == 0
    assert report["groups_excluded_without_exactly_two_reviewers"] == 1
    assert report["metrics"]["stance"]["cohen_kappa"] is None


def test_reader_rejects_unknown_and_duplicate_annotations(tmp_path: Path) -> None:
    path = tmp_path / "reliability.jsonl"
    first = annotation("record-001", "reviewer-001").model_dump(mode="json")
    unknown = deepcopy(first)
    unknown.update(record_id="missing-001", reviewer_id="reviewer-002")
    path.write_text(
        "\n".join((json.dumps(first), json.dumps(first), json.dumps(unknown))) + "\n",
        encoding="utf-8",
    )
    annotations, errors = read_reliability_jsonl(path, known_record_ids={"record-001"})
    assert len(annotations) == 1
    assert any("duplicate reviewer annotation" in error for error in errors)
    assert any("unknown evidence record" in error for error in errors)


def test_reliability_schema_drift_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "schema.json"
    path.write_text("{}", encoding="utf-8")
    try:
        validate_reliability_schema_current(path)
    except ValueError as exc:
        assert "out of date" in str(exc)
    else:
        raise AssertionError("schema drift was not rejected")
    path.write_text(json.dumps(canonical_reliability_schema()), encoding="utf-8")
    validate_reliability_schema_current(path)
