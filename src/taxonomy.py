"""Canonical controlled taxonomy generation and drift checks."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from .models import (
    ActorType,
    CertaintyTreatment,
    ClaimType,
    EvidenceKind,
    EvidenceTier,
    FrameLabel,
    PackagingSupport,
    ReviewStatus,
    SpeakerRole,
    StanceDirection,
    TopicLabel,
)

DEFAULT_TAXONOMY = Path("methodology/taxonomy.json")


def _values(enum_type: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_type]


def canonical_taxonomy() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "event_scope": "NEET 2026 protests",
        "stance_values": _values(StanceDirection),
        "actor_types": _values(ActorType),
        "speaker_roles": _values(SpeakerRole),
        "evidence_kinds": _values(EvidenceKind),
        "topic_labels": _values(TopicLabel),
        "frame_labels": _values(FrameLabel),
        "claim_types": _values(ClaimType),
        "certainty_treatments": _values(CertaintyTreatment),
        "packaging_support": _values(PackagingSupport),
        "evidence_tiers": {
            EvidenceTier.A.value: "timestamped spoken evidence with verified source and speaker",
            EvidenceTier.B.value: (
                "exact reliable quotation or attribution without complete audiovisual verification"
            ),
            EvidenceTier.C.value: "headline, thumbnail, description, or packaging evidence only",
            EvidenceTier.D.value: "mixed stream, unresolved identity, or insufficient attribution",
        },
        "review_states": _values(ReviewStatus),
    }


def load_taxonomy(path: Path = DEFAULT_TAXONOMY) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load taxonomy {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: taxonomy must be a JSON object")
    return payload


def validate_taxonomy_current(path: Path = DEFAULT_TAXONOMY) -> None:
    if load_taxonomy(path) != canonical_taxonomy():
        raise ValueError(f"{path} is out of date; run 'parallax taxonomy --write'")
