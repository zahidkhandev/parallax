"""Validated public evidence records for Project Parallax."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from hashlib import sha256

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


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


class ActorType(StrEnum):
    PROTEST_ORGANISER = "protest_organiser"
    STUDENT_CANDIDATE = "student_candidate"
    PARENT = "parent"
    GOVERNMENT_REPRESENTATIVE = "government_representative"
    EDUCATION_EXAM_AUTHORITY = "education_exam_authority"
    POLICE = "police"
    RULING_PARTY = "ruling_party"
    OPPOSITION_PARTY = "opposition_party"
    COURT_PUBLIC_INSTITUTION = "court_public_institution"
    ANCHOR_CORRESPONDENT = "anchor_correspondent"
    GUEST_EXPERT = "guest_expert"
    OTHER_RELEVANT_ACTOR = "other_relevant_actor"


class SpeakerRole(StrEnum):
    ANCHOR = "anchor"
    CORRESPONDENT = "correspondent"
    GUEST = "guest"
    EXPERT = "expert"
    INTERVIEWEE = "interviewee"
    VOICEOVER = "voiceover"
    QUOTED_SOURCE = "quoted_source"
    INSTITUTIONAL_STATEMENT = "institutional_statement"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EvidenceKind(StrEnum):
    SPOKEN = "spoken"
    HEADLINE = "headline"
    THUMBNAIL = "thumbnail"
    DESCRIPTION = "description"
    TICKER = "ticker"
    OTHER_PACKAGING = "other_packaging"


class ClaimType(StrEnum):
    OBSERVED_FACT = "observed_fact"
    VERIFIED_FACT = "verified_fact"
    REPORTED_ALLEGATION = "reported_allegation"
    SPEAKER_ALLEGATION = "speaker_allegation"
    OPINION = "opinion"
    QUESTION = "question"
    SPECULATION = "speculation"
    PREDICTION = "prediction"
    QUOTATION = "quotation"
    UNCLEAR = "unclear"


class CertaintyTreatment(StrEnum):
    EXPLICITLY_QUALIFIED = "explicitly_qualified"
    IMPLICITLY_QUALIFIED = "implicitly_qualified"
    ASSERTED_AS_FACT = "asserted_as_fact"
    CONTESTED = "contested"
    UNCLEAR = "unclear"


class PackagingSupport(StrEnum):
    SUPPORTED_BY_BODY = "supported_by_body"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED_IN_REVIEWED_PORTION = "unsupported_in_reviewed_portion"
    CONTRADICTED_BY_BODY = "contradicted_by_body"
    INSUFFICIENT_TRANSCRIPT = "insufficient_transcript"
    NOT_REVIEWED = "not_reviewed"
    NOT_APPLICABLE = "not_applicable"


class TopicLabel(StrEnum):
    PROTEST_DEMANDS = "protest_demands"
    STUDENT_CANDIDATE_EXPERIENCE = "student_candidate_experience"
    PARENT_RESPONSE = "parent_response"
    EXAMINATION_ADMINISTRATION = "examination_administration"
    GOVERNMENT_RESPONSE = "government_response"
    POLICING_PUBLIC_ORDER = "policing_public_order"
    PARTY_POLITICS = "party_politics"
    COURTS_LEGAL_PROCESS = "courts_legal_process"
    PUBLIC_DISRUPTION = "public_disruption"
    EVIDENCE_VERIFICATION = "evidence_verification"
    OTHER_RELEVANT = "other_relevant"


class FrameLabel(StrEnum):
    LEGITIMISING = "legitimising"
    DELEGITIMISING = "delegitimising"
    CRIMINALISING = "criminalising"
    VICTIMISING = "victimising"
    HEROISING = "heroising"
    LAW_AND_ORDER = "law_and_order"
    CIVIL_RIGHTS = "civil_rights"
    INSTITUTIONAL_ACCOUNTABILITY = "institutional_accountability"
    INSTITUTIONAL_TRUST = "institutional_trust"
    PUBLIC_DISRUPTION = "public_disruption"
    ELECTORAL_POLITICAL = "electoral_political"
    PROCEDURAL_LEGAL = "procedural_legal"
    HUMAN_INTEREST = "human_interest"
    EVIDENCE_VERIFICATION = "evidence_verification"
    OTHER = "other"


class Speaker(StrictModel):
    name: str | None = Field(default=None, max_length=200)
    role: SpeakerRole
    affiliation: str | None = Field(default=None, max_length=200)
    represented_actor_type: ActorType | None = None


class TargetActor(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    actor_type: ActorType


class LoadedLanguage(StrictModel):
    term: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=500)


class EvidenceSegment(StrictModel):
    """One timestamped spoken or packaging observation, never an outlet-wide verdict."""

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    record_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,99}$")
    source_url: HttpUrl
    outlet: str = Field(min_length=1, max_length=200)
    programme: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    published_at: AwareDatetime | None = None
    accessed_at: AwareDatetime
    evidence_kind: EvidenceKind
    segment_start_seconds: float = Field(ge=0)
    segment_end_seconds: float = Field(gt=0)
    speaker: Speaker
    attributed_sources: list[str] = Field(default_factory=list, max_length=20)
    target_actor: TargetActor
    topic_labels: list[TopicLabel] = Field(min_length=1, max_length=20)
    excerpt: str = Field(min_length=1, max_length=500)
    original_language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$")
    translation: str | None = Field(default=None, max_length=500)
    stance: StanceDirection
    frame_labels: list[FrameLabel] = Field(default_factory=list, max_length=20)
    loaded_language: list[LoadedLanguage] = Field(default_factory=list, max_length=20)
    claim_type: ClaimType
    certainty: CertaintyTreatment
    allegation_qualified: bool | None = None
    packaging_support: PackagingSupport
    evidence_tier: EvidenceTier
    transcript_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    review_status: ReviewStatus
    reviewed_at: AwareDatetime | None = None
    reviewer_ids: list[str] = Field(default_factory=list, max_length=2)
    context_notes: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def enforce_evidence_rules(self) -> EvidenceSegment:
        if self.segment_end_seconds <= self.segment_start_seconds:
            raise ValueError("segment_end_seconds must be greater than segment_start_seconds")
        if len(set(self.topic_labels)) != len(self.topic_labels):
            raise ValueError("topic_labels must not contain duplicates")
        if len(set(self.frame_labels)) != len(self.frame_labels):
            raise ValueError("frame_labels must not contain duplicates")
        packaging = self.evidence_kind is not EvidenceKind.SPOKEN
        if packaging and self.evidence_tier is not EvidenceTier.C:
            raise ValueError("packaging evidence must use evidence tier C")
        if not packaging and self.packaging_support is not PackagingSupport.NOT_APPLICABLE:
            raise ValueError("spoken evidence must use packaging_support 'not_applicable'")
        allegation = self.claim_type in {
            ClaimType.REPORTED_ALLEGATION,
            ClaimType.SPEAKER_ALLEGATION,
        }
        if allegation != (self.allegation_qualified is not None):
            raise ValueError("allegation_qualified is required only for allegation claim types")
        required_reviewers = {
            ReviewStatus.MACHINE_ONLY: 0,
            ReviewStatus.HUMAN_REVIEWED: 1,
            ReviewStatus.SECOND_REVIEWED: 2,
            ReviewStatus.REJECTED: 1,
        }[self.review_status]
        if len(set(self.reviewer_ids)) != len(self.reviewer_ids):
            raise ValueError("reviewer_ids must be distinct")
        if len(self.reviewer_ids) != required_reviewers:
            message = f"{self.review_status.value} requires {required_reviewers} reviewer(s)"
            raise ValueError(message)
        if (self.review_status is ReviewStatus.MACHINE_ONLY) != (self.reviewed_at is None):
            raise ValueError("reviewed_at is required for reviewed or rejected records only")
        return self


class DatasetStatus(StrEnum):
    SCAFFOLD = "scaffold_no_observations"
    COLLECTION = "collection"
    REVIEW = "review"
    PUBLISHED = "published"


class CollectionManifest(StrictModel):
    """Versioned declaration of the public dataset's scope and release state."""

    project: str = Field(pattern=r"^Project Parallax$")
    repository: str = Field(pattern=r"^neet-protest-2026-media-analysis$")
    dataset: str = Field(pattern=r"^NEET Protest 2026 Media Analysis$")
    dataset_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    methodology_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    taxonomy_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    schema_version: str = Field(pattern=r"^1\.0\.0$")
    status: DatasetStatus
    collection_start: date | None
    collection_end: date | None
    included_event: str = Field(pattern=r"^NEET 2026 protests$")
    record_count: int = Field(ge=0)
    generated_at: AwareDatetime | None = None
    notes: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def enforce_release_state(self) -> CollectionManifest:
        dates = (self.collection_start, self.collection_end)
        if dates[0] is None and dates[1] is not None:
            raise ValueError("collection_end requires collection_start")
        if dates[0] is not None and dates[1] is not None and dates[1] < dates[0]:
            raise ValueError("collection_end must not precede collection_start")
        if self.status is DatasetStatus.PUBLISHED and (
            dates[0] is None or dates[1] is None or self.generated_at is None
        ):
            message = "published datasets require a closed collection window and generated_at"
            raise ValueError(message)
        if self.status is DatasetStatus.SCAFFOLD and self.record_count != 0:
            raise ValueError("scaffold_no_observations requires record_count 0")
        return self


class CorrectionRecord(StrictModel):
    """One append-only correction to a previously published evidence field."""

    correction_id: str = Field(pattern=r"^cor-[a-z0-9][a-z0-9._-]{2,95}$")
    record_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,99}$")
    corrected_at: AwareDatetime
    field: str = Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
    original_value: str = Field(max_length=2000)
    corrected_value: str = Field(max_length=2000)
    reason: str = Field(min_length=1, max_length=1000)
    reviewer: str = Field(min_length=1, max_length=100)
    metrics_affected: bool

    @field_validator("metrics_affected", mode="before")
    @classmethod
    def parse_metrics_affected(cls, value: object) -> object:
        if isinstance(value, bool):
            return value
        if value == "true":
            return True
        if value == "false":
            return False
        raise ValueError("metrics_affected must be 'true' or 'false'")

    @model_validator(mode="after")
    def require_a_change(self) -> CorrectionRecord:
        if self.original_value == self.corrected_value:
            raise ValueError("original_value and corrected_value must differ")
        return self


def transcript_digest(text: str) -> str:
    """Return a reproducible hash without publishing a complete working transcript."""
    return sha256(text.encode("utf-8")).hexdigest()
