"""Transparent descriptive aggregates for validated evidence records."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from .analysis_models import AnalysisSummary
from .models import EvidenceSegment, ReviewStatus

PUBLISHABLE_REVIEW_STATES = {ReviewStatus.HUMAN_REVIEWED, ReviewStatus.SECOND_REVIEWED}


@dataclass(frozen=True)
class AnalysisOptions:
    include_machine_only: bool = False
    include_rejected: bool = False


@dataclass(frozen=True)
class AnalysisProvenance:
    dataset_version: str
    methodology_version: str
    taxonomy_version: str
    schema_version: str
    evidence_sha256: str
    correction_count: int
    report_start: str
    report_through: str
    collection_end: str | None


@dataclass(frozen=True)
class SegmentKey:
    source_url: str
    evidence_kind: str
    start_seconds: float
    end_seconds: float


def include_record(record: EvidenceSegment, options: AnalysisOptions) -> bool:
    """Apply the shared publication filter used by metrics and evidence reports."""
    if record.review_status is ReviewStatus.REJECTED:
        return options.include_rejected
    if record.review_status is ReviewStatus.MACHINE_ONLY:
        return options.include_machine_only
    return record.review_status in PUBLISHABLE_REVIEW_STATES


def segment_key(record: EvidenceSegment) -> SegmentKey:
    """Identify source material independently from its target-specific annotations."""
    return SegmentKey(
        source_url=str(record.source_url),
        evidence_kind=record.evidence_kind.value,
        start_seconds=record.segment_start_seconds,
        end_seconds=record.segment_end_seconds,
    )


def _group_segments(
    records: Iterable[EvidenceSegment],
) -> dict[SegmentKey, list[EvidenceSegment]]:
    groups: dict[SegmentKey, list[EvidenceSegment]] = defaultdict(list)
    for record in records:
        groups[segment_key(record)].append(record)
    return dict(groups)


def _nested_counts(pairs: Iterable[tuple[str, str]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for group, value in pairs:
        counts[group][value] += 1
    return {group: dict(sorted(values.items())) for group, values in sorted(counts.items())}


def _nested_counter(counts: Counter[tuple[str, str]]) -> dict[str, dict[str, int]]:
    nested: dict[str, dict[str, int]] = defaultdict(dict)
    for (group, value), count in sorted(counts.items()):
        nested[group][value] = count
    return dict(nested)


def _outlet_target_stance(
    records: Iterable[EvidenceSegment],
) -> dict[str, dict[str, dict[str, int]]]:
    counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for record in records:
        counts[record.outlet][record.target_actor.actor_type.value][record.stance.value] += 1
    return {
        outlet: {
            target: dict(sorted(stances.items()))
            for target, stances in sorted(targets.items())
        }
        for outlet, targets in sorted(counts.items())
    }


def _rounded_counts(counts: Counter[str]) -> dict[str, float]:
    return {key: round(value, 3) for key, value in sorted(counts.items())}


def build_summary(
    records: Iterable[EvidenceSegment],
    options: AnalysisOptions | None = None,
    provenance: AnalysisProvenance | None = None,
) -> dict[str, Any]:
    """Build count-based metrics with explicit populations and no composite score."""
    options = options or AnalysisOptions()
    all_records = list(records)

    included = [record for record in all_records if include_record(record, options)]
    segments = _group_segments(included)

    review_counts = Counter(record.review_status.value for record in all_records)
    tier_counts = Counter(record.evidence_tier.value for record in included)
    topic_counts: Counter[str] = Counter()
    frame_counts: Counter[str] = Counter()
    speaker_roles: Counter[str] = Counter()
    attributed_sources: Counter[str] = Counter()
    loaded_terms: Counter[str] = Counter()
    topic_seconds: Counter[str] = Counter()
    frame_seconds: Counter[str] = Counter()
    speaker_seconds: Counter[str] = Counter()
    outlet_segments: Counter[str] = Counter()
    language_segments: Counter[str] = Counter()
    packaging_support: Counter[str] = Counter()
    tier_segments: Counter[str] = Counter()
    claim_certainty: Counter[tuple[str, str]] = Counter()
    allegation_qualification: Counter[str] = Counter()
    conflict_counts: Counter[str] = Counter()
    spoken_duration = 0.0
    for key, group in segments.items():
        topics = {topic.value for record in group for topic in record.topic_labels}
        frames = {frame.value for record in group for frame in record.frame_labels}
        sources = {source for record in group for source in record.attributed_sources}
        terms = {item.term.casefold() for record in group for item in record.loaded_language}
        topic_counts.update(topics)
        frame_counts.update(frames)
        attributed_sources.update(sources)
        loaded_terms.update(terms)

        outlets = {record.outlet for record in group}
        roles = {record.speaker.role.value for record in group}
        languages = {record.original_language for record in group}
        outlet = next(iter(outlets)) if len(outlets) == 1 else "conflicting_annotations"
        role = next(iter(roles)) if len(roles) == 1 else "conflicting_annotations"
        outlet_segments[outlet] += 1
        speaker_roles[role] += 1
        language = (
            next(iter(languages)) if len(languages) == 1 else "conflicting_annotations"
        )
        language_segments[language] += 1
        if len(outlets) > 1:
            conflict_counts["outlet"] += 1
        if len(roles) > 1:
            conflict_counts["speaker_role"] += 1
        if len(languages) > 1:
            conflict_counts["original_language"] += 1
        tiers = {record.evidence_tier.value for record in group}
        tier = next(iter(tiers)) if len(tiers) == 1 else "conflicting_annotations"
        tier_segments[tier] += 1
        if len(tiers) > 1:
            conflict_counts["evidence_tier"] += 1

        claim_pairs = {(record.claim_type.value, record.certainty.value) for record in group}
        if len(claim_pairs) == 1:
            claim_certainty[next(iter(claim_pairs))] += 1
        else:
            claim_certainty[("conflicting_annotations", "conflicting_annotations")] += 1
            conflict_counts["claim_certainty"] += 1
        allegations = [
            record
            for record in group
            if record.claim_type.value in {"reported_allegation", "speaker_allegation"}
        ]
        if allegations:
            qualifications = {record.allegation_qualified for record in allegations}
            if len(qualifications) == 1:
                qualification = next(iter(qualifications))
                allegation_qualification["qualified" if qualification else "unqualified"] += 1
            else:
                allegation_qualification["conflicting_annotations"] += 1
                conflict_counts["allegation_qualification"] += 1

        if key.evidence_kind == "spoken":
            duration = key.end_seconds - key.start_seconds
            spoken_duration += duration
            speaker_seconds[role] += duration
            for topic in topics:
                topic_seconds[topic] += duration
            for frame in frames:
                frame_seconds[frame] += duration
        else:
            support_values = {record.packaging_support.value for record in group}
            support = (
                next(iter(support_values))
                if len(support_values) == 1
                else "conflicting_annotations"
            )
            packaging_support[support] += 1
            if len(support_values) > 1:
                conflict_counts["packaging_support"] += 1
    reviewed = sum(
        record.review_status is not ReviewStatus.MACHINE_ONLY for record in all_records
    )

    payload = {
        "metric_version": "1.0.0",
        "options": asdict(options),
        "provenance": asdict(provenance) if provenance is not None else None,
        "population": {
            "all_records": len(all_records),
            "included_records": len(included),
            "included_distinct_segments": len(segments),
            "additional_target_records": len(included) - len(segments),
            "excluded_records": len(all_records) - len(included),
            "reviewed_records": reviewed,
            "human_review_coverage": reviewed / len(all_records) if all_records else None,
            "included_spoken_duration_seconds": round(
                spoken_duration,
                3,
            ),
        },
        "review_state_counts": dict(sorted(review_counts.items())),
        "evidence_tier_counts": dict(sorted(tier_counts.items())),
        "evidence_tier_segment_counts": dict(sorted(tier_segments.items())),
        "stance_by_target_actor": _nested_counts(
            (record.target_actor.name, record.stance.value) for record in included
        ),
        "stance_by_target_type": _nested_counts(
            (record.target_actor.actor_type.value, record.stance.value) for record in included
        ),
        "stance_by_outlet_and_target_type": _outlet_target_stance(included),
        "speaker_role_counts": dict(sorted(speaker_roles.items())),
        "speaker_role_duration_seconds": _rounded_counts(speaker_seconds),
        "outlet_record_counts": dict(
            sorted(Counter(record.outlet for record in included).items())
        ),
        "outlet_segment_counts": dict(sorted(outlet_segments.items())),
        "original_language_segment_counts": dict(sorted(language_segments.items())),
        "attributed_source_counts": dict(sorted(attributed_sources.items())),
        "topic_record_counts": dict(sorted(topic_counts.items())),
        "topic_duration_seconds": _rounded_counts(topic_seconds),
        "frame_segment_counts": dict(sorted(frame_counts.items())),
        "frame_duration_seconds": _rounded_counts(frame_seconds),
        "loaded_language_term_counts": dict(sorted(loaded_terms.items())),
        "claim_by_certainty": _nested_counter(claim_certainty),
        "allegation_qualification_counts": {
            "qualified": allegation_qualification["qualified"],
            "unqualified": allegation_qualification["unqualified"],
            "conflicting_annotations": allegation_qualification["conflicting_annotations"],
            "total_allegations": sum(allegation_qualification.values()),
        },
        "packaging_support_counts": dict(sorted(packaging_support.items())),
        "segment_annotation_conflict_counts": dict(sorted(conflict_counts.items())),
        "notes": [
            "Counts describe included evidence segments, not truth, motive, or character.",
            "Target, speaker, and source dimensions remain separate.",
            "No composite or universal bias score is calculated.",
            "Topic durations are non-exclusive when a segment has multiple topic labels.",
            "Coverage metrics deduplicate source URL, evidence kind, and exact timestamps.",
            "Stance metrics retain separate records because every stance has one target actor.",
        ],
    }
    return AnalysisSummary.model_validate(payload).model_dump(mode="json")
