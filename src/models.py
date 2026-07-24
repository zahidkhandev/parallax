from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class EvidenceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ReviewStatus(StrEnum):
    MACHINE_ONLY = "machine_only"
    HUMAN_REVIEWED = "human_reviewed"
    SECOND_REVIEWED = "second_reviewed"
    REJECTED = "rejected"


class StanceDirection(StrEnum):
    FAVOURABLE = "favourable"
    CRITICAL = "critical"
    NEUTRAL_DESCRIPTIVE = "neutral_descriptive"
    MIXED = "mixed"
    UNCLEAR = "unclear"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceSegment(BaseModel):
    record_id: str
    source_url: HttpUrl
    video_id: str | None = None
    outlet: str
    programme: str | None = None
    published_at: datetime | None = None

    segment_start_seconds: float = Field(ge=0)
    segment_end_seconds: float = Field(gt=0)

    speaker_name: str | None = None
    speaker_role: str
    target_entity: str

    excerpt: str = Field(min_length=1, max_length=500)
    original_language: str
    translation: str | None = None

    stance_direction: StanceDirection
    frames: list[str] = Field(default_factory=list)
    claim_type: str
    certainty_treatment: str
    evidence_tier: EvidenceTier
    review_status: ReviewStatus

    transcript_source: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    reviewer_notes: str | None = None

    def model_post_init(self, __context: object) -> None:
        if self.segment_end_seconds <= self.segment_start_seconds:
            raise ValueError("segment_end_seconds must be greater than segment_start_seconds")
