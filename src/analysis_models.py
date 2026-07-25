"""Versioned contract for public analytical artifacts."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
CountMap = dict[str, NonNegativeInt]
DurationMap = dict[str, NonNegativeFloat]
NestedCountMap = dict[str, CountMap]
TripleCountMap = dict[str, NestedCountMap]
DEFAULT_ANALYSIS_SCHEMA = Path("schemas/analysis-summary.schema.json")


class StrictAnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisOptionsModel(StrictAnalysisModel):
    include_machine_only: bool
    include_rejected: bool


class AnalysisProvenanceModel(StrictAnalysisModel):
    dataset_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    methodology_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    taxonomy_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    correction_count: NonNegativeInt
    report_start: date
    report_through: date
    collection_end: date | None

    @model_validator(mode="after")
    def validate_window(self) -> AnalysisProvenanceModel:
        if self.report_through < self.report_start:
            raise ValueError("report_through must not precede report_start")
        if self.collection_end is not None and self.report_through > self.collection_end:
            raise ValueError("report_through must not exceed collection_end")
        return self


class AnalysisPopulation(StrictAnalysisModel):
    all_records: NonNegativeInt
    included_records: NonNegativeInt
    included_distinct_segments: NonNegativeInt
    additional_target_records: NonNegativeInt
    excluded_records: NonNegativeInt
    reviewed_records: NonNegativeInt
    human_review_coverage: Annotated[float, Field(ge=0, le=1)] | None
    included_spoken_duration_seconds: NonNegativeFloat

    @model_validator(mode="after")
    def validate_totals(self) -> AnalysisPopulation:
        if self.included_records + self.excluded_records != self.all_records:
            raise ValueError("included_records + excluded_records must equal all_records")
        target_record_count = self.included_records - self.included_distinct_segments
        if target_record_count != self.additional_target_records:
            raise ValueError(
                "included_records - included_distinct_segments must equal additional_target_records"
            )
        if self.included_distinct_segments > self.included_records:
            raise ValueError("included_distinct_segments cannot exceed included_records")
        if self.reviewed_records > self.all_records:
            raise ValueError("reviewed_records cannot exceed all_records")
        expected = self.reviewed_records / self.all_records if self.all_records else None
        if expected is None and self.human_review_coverage is not None:
            raise ValueError("empty populations require null human_review_coverage")
        if expected is not None and (
            self.human_review_coverage is None
            or abs(self.human_review_coverage - expected) > 1e-12
        ):
            raise ValueError("human_review_coverage must equal reviewed_records / all_records")
        return self


class AllegationQualificationCounts(StrictAnalysisModel):
    qualified: NonNegativeInt
    unqualified: NonNegativeInt
    conflicting_annotations: NonNegativeInt
    total_allegations: NonNegativeInt

    @model_validator(mode="after")
    def validate_total(self) -> AllegationQualificationCounts:
        components = self.qualified + self.unqualified + self.conflicting_annotations
        if components != self.total_allegations:
            raise ValueError("allegation qualification components must equal total_allegations")
        return self


class AnalysisSummary(StrictAnalysisModel):
    metric_version: str = Field(pattern=r"^1\.0\.0$")
    options: AnalysisOptionsModel
    provenance: AnalysisProvenanceModel | None
    population: AnalysisPopulation
    review_state_counts: CountMap
    evidence_tier_counts: CountMap
    evidence_tier_segment_counts: CountMap
    stance_by_target_actor: NestedCountMap
    stance_by_target_type: NestedCountMap
    stance_by_outlet_and_target_type: TripleCountMap
    speaker_role_counts: CountMap
    speaker_role_duration_seconds: DurationMap
    outlet_record_counts: CountMap
    outlet_segment_counts: CountMap
    original_language_segment_counts: CountMap
    attributed_source_counts: CountMap
    topic_record_counts: CountMap
    topic_duration_seconds: DurationMap
    frame_segment_counts: CountMap
    frame_duration_seconds: DurationMap
    loaded_language_term_counts: CountMap
    claim_by_certainty: NestedCountMap
    allegation_qualification_counts: AllegationQualificationCounts
    packaging_support_counts: CountMap
    segment_annotation_conflict_counts: CountMap
    notes: list[str] = Field(min_length=1)


def canonical_analysis_schema() -> dict[str, Any]:
    schema = AnalysisSummary.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://project-parallax.example/schemas/analysis-summary.schema.json"
    return schema


def validate_analysis_schema_current(path: Path = DEFAULT_ANALYSIS_SCHEMA) -> None:
    try:
        checked_in = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load analysis schema {path}: {exc}") from exc
    if checked_in != canonical_analysis_schema():
        raise ValueError(f"{path} is out of date; run 'parallax analysis-schema --write'")
