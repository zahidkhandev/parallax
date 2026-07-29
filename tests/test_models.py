import pytest
from pydantic import ValidationError

from src.models import EvidenceSegment, transcript_digest


def valid_record() -> dict:
    return {
        "schema_version": "1.0.0",
        "record_id": "test-segment-001",
        "source_url": "https://example.org/media-item",
        "outlet": "Test outlet",
        "programme": "Test programme",
        "title": "Synthetic test fixture concerning the NEET 2026 protests",
        "published_at": "2026-05-01T09:00:00+05:30",
        "accessed_at": "2026-05-02T10:00:00Z",
        "evidence_kind": "spoken",
        "segment_start_seconds": 10.0,
        "segment_end_seconds": 20.0,
        "speaker": {
            "name": "Test speaker",
            "role": "guest",
            "affiliation": "Test organisation",
            "represented_actor_type": "guest_expert",
        },
        "attributed_sources": ["Test document"],
        "target_actor": {"name": "Test authority", "actor_type": "education_exam_authority"},
        "topic_labels": ["examination_administration"],
        "excerpt": "A short synthetic excerpt used only to test validation.",
        "original_language": "en",
        "translation": None,
        "stance": "neutral_descriptive",
        "frame_labels": ["procedural_legal"],
        "loaded_language": [],
        "claim_type": "observed_fact",
        "certainty": "explicitly_qualified",
        "allegation_qualified": None,
        "packaging_support": "not_applicable",
        "evidence_tier": "A",
        "transcript_sha256": "a" * 64,
        "review_status": "human_reviewed",
        "reviewed_at": "2026-05-03T10:00:00Z",
        "reviewer_ids": ["reviewer-001"],
        "context_notes": "Synthetic test fixture; it is not a factual media observation.",
    }


def test_valid_record_preserves_guest_attribution() -> None:
    record = EvidenceSegment.model_validate(valid_record())
    assert record.speaker.role.value == "guest"
    assert record.target_actor.name == "Test authority"


def test_end_must_follow_start() -> None:
    payload = valid_record()
    payload["segment_end_seconds"] = 5.0
    with pytest.raises(ValidationError, match="must be greater"):
        EvidenceSegment.model_validate(payload)


def test_every_stance_requires_nonempty_target_actor() -> None:
    payload = valid_record()
    payload["target_actor"]["name"] = ""
    with pytest.raises(ValidationError):
        EvidenceSegment.model_validate(payload)


def test_allegation_requires_qualification_assessment() -> None:
    payload = valid_record()
    payload["claim_type"] = "reported_allegation"
    with pytest.raises(ValidationError, match="allegation_qualified"):
        EvidenceSegment.model_validate(payload)
    payload["allegation_qualified"] = False
    assert EvidenceSegment.model_validate(payload).allegation_qualified is False


def test_packaging_is_tier_c_and_records_support() -> None:
    payload = valid_record()
    payload.update(
        evidence_kind="headline",
        evidence_tier="C",
        packaging_support="partially_supported",
    )
    assert EvidenceSegment.model_validate(payload).evidence_tier.value == "C"
    payload["evidence_tier"] = "A"
    with pytest.raises(ValidationError, match="tier C"):
        EvidenceSegment.model_validate(payload)


def test_review_state_enforces_distinct_reviewer_count() -> None:
    payload = valid_record()
    payload["review_status"] = "second_reviewed"
    payload["reviewer_ids"] = ["reviewer-001", "reviewer-001"]
    with pytest.raises(ValidationError, match="distinct"):
        EvidenceSegment.model_validate(payload)
    payload["reviewer_ids"] = ["reviewer-001", "reviewer-002"]
    assert EvidenceSegment.model_validate(payload).review_status.value == "second_reviewed"


def test_unknown_fields_are_rejected() -> None:
    payload = valid_record()
    payload["opaque_bias_score"] = 0.8
    with pytest.raises(ValidationError, match="Extra inputs"):
        EvidenceSegment.model_validate(payload)


def test_transcript_digest_is_stable_without_retaining_text() -> None:
    assert transcript_digest("working transcript") == transcript_digest("working transcript")
    assert len(transcript_digest("working transcript")) == 64


def test_datetimes_must_include_timezone() -> None:
    payload = valid_record()
    payload["accessed_at"] = "2026-05-02T10:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        EvidenceSegment.model_validate(payload)


def test_topic_and_frame_labels_are_controlled_and_unique() -> None:
    payload = valid_record()
    payload["topic_labels"] = ["not_a_topic"]
    with pytest.raises(ValidationError):
        EvidenceSegment.model_validate(payload)

    payload = valid_record()
    payload["frame_labels"] = ["procedural_legal", "procedural_legal"]
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        EvidenceSegment.model_validate(payload)
