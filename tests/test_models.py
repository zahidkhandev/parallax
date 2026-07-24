import pytest
from pydantic import ValidationError

from src.models import EvidenceSegment


def valid_record() -> dict:
    return {
        "record_id": "example-001",
        "source_url": "https://www.youtube.com/watch?v=example",
        "video_id": "example",
        "outlet": "Example Outlet",
        "programme": "Example Programme",
        "segment_start_seconds": 10.0,
        "segment_end_seconds": 20.0,
        "speaker_role": "anchor",
        "target_entity": "protest_participants",
        "excerpt": "A short example excerpt.",
        "original_language": "en",
        "stance_direction": "neutral_descriptive",
        "frames": ["procedural_legal"],
        "claim_type": "observed_fact",
        "certainty_treatment": "explicitly_qualified",
        "evidence_tier": "A",
        "review_status": "human_reviewed",
    }


def test_valid_record() -> None:
    record = EvidenceSegment.model_validate(valid_record())
    assert record.record_id == "example-001"


def test_end_must_follow_start() -> None:
    record = valid_record()
    record["segment_end_seconds"] = 5.0
    with pytest.raises(ValidationError):
        EvidenceSegment.model_validate(record)
