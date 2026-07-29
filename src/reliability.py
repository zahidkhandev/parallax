"""Independent annotation validation and per-label reliability metrics."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .models import (
    ActorType,
    CertaintyTreatment,
    ClaimType,
    EvidenceTier,
    FrameLabel,
    SpeakerRole,
    StanceDirection,
    TopicLabel,
)

DEFAULT_RELIABILITY_DATA = Path("public-data/reliability-annotations.jsonl")
DEFAULT_RELIABILITY_SCHEMA = Path("schemas/reliability-annotation.schema.json")


class ReliabilityAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    annotation_version: str = Field(pattern=r"^1\.0\.0$")
    record_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,99}$")
    reviewer_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,99}$")
    round_id: str = Field(min_length=1, max_length=100)
    target_actor_name: str = Field(min_length=1, max_length=200)
    target_actor_type: ActorType
    speaker_role: SpeakerRole
    stance: StanceDirection
    claim_type: ClaimType
    certainty: CertaintyTreatment
    evidence_tier: EvidenceTier
    topic_labels: list[TopicLabel] = Field(min_length=1, max_length=20)
    frame_labels: list[FrameLabel] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_labels(self) -> ReliabilityAnnotation:
        if len(set(self.topic_labels)) != len(self.topic_labels):
            raise ValueError("topic_labels must not contain duplicates")
        if len(set(self.frame_labels)) != len(self.frame_labels):
            raise ValueError("frame_labels must not contain duplicates")
        return self


def canonical_reliability_schema() -> dict[str, Any]:
    schema = ReliabilityAnnotation.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = (
        "https://project-parallax.example/schemas/reliability-annotation.schema.json"
    )
    return schema


def validate_reliability_schema_current(
    path: Path = DEFAULT_RELIABILITY_SCHEMA,
) -> None:
    try:
        checked_in = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load reliability schema {path}: {exc}") from exc
    if checked_in != canonical_reliability_schema():
        raise ValueError(f"{path} is out of date; run 'parallax reliability-schema --write'")


def read_reliability_jsonl(
    path: Path, *, known_record_ids: set[str]
) -> tuple[list[ReliabilityAnnotation], list[str]]:
    annotations: list[ReliabilityAnnotation] = []
    errors: list[str] = []
    identities: set[tuple[str, str, str]] = set()
    try:
        handle = path.open(encoding="utf-8")
    except OSError as exc:
        return annotations, [f"Cannot read {path}: {exc}"]
    with handle:
        for line_number, raw in enumerate(handle, 1):
            location = f"{path}:{line_number}"
            if not raw.strip():
                errors.append(f"{location}: blank lines are not valid JSONL records")
                continue
            try:
                annotation = ReliabilityAnnotation.model_validate_json(raw)
            except (ValidationError, ValueError) as exc:
                errors.append(f"{location}: {exc}")
                continue
            identity = (annotation.round_id, annotation.record_id, annotation.reviewer_id)
            if identity in identities:
                errors.append(f"{location}: duplicate reviewer annotation {identity!r}")
                continue
            identities.add(identity)
            if annotation.record_id not in known_record_ids:
                errors.append(f"{location}: unknown evidence record {annotation.record_id!r}")
                continue
            annotations.append(annotation)
    return annotations, errors


def _cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    observed = sum(left == right for left, right in pairs) / len(pairs)
    left_counts = Counter(left for left, _ in pairs)
    right_counts = Counter(right for _, right in pairs)
    expected = sum(
        left_counts[label] / len(pairs) * right_counts[label] / len(pairs)
        for label in left_counts.keys() | right_counts.keys()
    )
    if expected == 1:
        return 1.0 if observed == 1 else None
    return round((observed - expected) / (1 - expected), 6)


def build_reliability_report(annotations: list[ReliabilityAnnotation]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[ReliabilityAnnotation]] = defaultdict(list)
    for annotation in annotations:
        grouped[(annotation.round_id, annotation.record_id)].append(annotation)
    pairs = [
        sorted(group, key=lambda item: item.reviewer_id)
        for group in grouped.values()
        if len(group) == 2
    ]
    excluded = sum(len(group) != 2 for group in grouped.values())
    categorical = (
        "target_actor_name",
        "target_actor_type",
        "speaker_role",
        "stance",
        "claim_type",
        "certainty",
        "evidence_tier",
    )
    metrics: dict[str, Any] = {}
    for field in categorical:
        values = [(str(getattr(pair[0], field)), str(getattr(pair[1], field))) for pair in pairs]
        metrics[field] = {
            "pair_count": len(values),
            "percent_agreement": (
                round(sum(left == right for left, right in values) / len(values), 6)
                if values
                else None
            ),
            "cohen_kappa": _cohen_kappa(values),
        }
    for field in ("topic_labels", "frame_labels"):
        scores = []
        exact = 0
        for left, right in pairs:
            left_set = {str(item) for item in getattr(left, field)}
            right_set = {str(item) for item in getattr(right, field)}
            exact += left_set == right_set
            union = left_set | right_set
            scores.append(len(left_set & right_set) / len(union) if union else 1.0)
        metrics[field] = {
            "pair_count": len(scores),
            "exact_agreement": round(exact / len(scores), 6) if scores else None,
            "mean_jaccard": round(sum(scores) / len(scores), 6) if scores else None,
        }
    return {
        "reliability_version": "1.0.0",
        "annotation_count": len(annotations),
        "double_coded_pair_count": len(pairs),
        "groups_excluded_without_exactly_two_reviewers": excluded,
        "metrics": metrics,
        "notes": [
            "Metrics are reported per label and are not combined into one score.",
            "Agreement measures consistency, not correctness or political neutrality.",
        ],
    }
