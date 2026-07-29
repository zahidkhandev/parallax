"""Generate conservative machine-only headline packaging evidence.

The generator intentionally limits itself to metadata already accepted into the
source inventory. It does not claim to have reviewed article bodies, audio, or
video. Its outputs remain ``machine_only`` and are excluded from default public
analytics.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .inventory import (
    AvailabilityStatus,
    EligibilityStatus,
    SourceInventoryRecord,
    read_inventory,
)
from .models import (
    ActorType,
    CertaintyTreatment,
    ClaimType,
    EvidenceKind,
    EvidenceSegment,
    EvidenceTier,
    FrameLabel,
    LoadedLanguage,
    PackagingSupport,
    ReviewStatus,
    Speaker,
    SpeakerRole,
    StanceDirection,
    TargetActor,
    TopicLabel,
)

DEFAULT_INVENTORY = Path("public-data/source-inventory.jsonl")
DEFAULT_DATA = Path("public-data/evidence-segments.jsonl")
DEFAULT_MANIFEST = Path("public-data/collection-manifest.json")
DEFAULT_REPORT = Path("build/automated-evidence-report.json")
AUTOMATED_PREFIX = "auto-headline-"
PIPELINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class TargetRule:
    pattern: re.Pattern[str]
    name: str
    actor_type: ActorType


def _pattern(value: str) -> re.Pattern[str]:
    return re.compile(value, re.IGNORECASE)


TARGET_RULES = (
    TargetRule(_pattern(r"\bdharmendra\s+pradhan\b|धर्मेंद्र\s+प्रधान"), "Dharmendra Pradhan", ActorType.GOVERNMENT_REPRESENTATIVE),
    TargetRule(_pattern(r"\bsonam\s+wangchuk\b|सोनम\s+वांगचुक"), "Sonam Wangchuk", ActorType.PROTEST_ORGANISER),
    TargetRule(
        _pattern(r"\bnational testing agency\b|\bnta\b|एनटीए|राष्ट्रीय परीक्षा एजेंसी"),
        "National Testing Agency (NTA)",
        ActorType.EDUCATION_EXAM_AUTHORITY,
    ),
    TargetRule(
        _pattern(r"\bministry of education\b|\beducation ministry\b|शिक्षा मंत्रालय"),
        "Ministry of Education",
        ActorType.EDUCATION_EXAM_AUTHORITY,
    ),
    TargetRule(
        _pattern(r"\beducation minister\b|शिक्षा मंत्री"),
        "Union Education Minister",
        ActorType.GOVERNMENT_REPRESENTATIVE,
    ),
    TargetRule(
        _pattern(r"\bunion government\b|\bcentral government\b|\bcentre\b|केंद्र सरकार|सरकार"),
        "Union Government",
        ActorType.GOVERNMENT_REPRESENTATIVE,
    ),
    TargetRule(_pattern(r"\bpolice\b|पुलिस"), "Police", ActorType.POLICE),
    TargetRule(
        _pattern(r"\bsupreme court\b|\bcji\b|सुप्रीम कोर्ट|मुख्य न्यायाधीश"),
        "Supreme Court of India",
        ActorType.COURT_PUBLIC_INSTITUTION,
    ),
    TargetRule(
        _pattern(r"\bcentral bureau of investigation\b|\bcbi\b|सीबीआई"),
        "Central Bureau of Investigation (CBI)",
        ActorType.COURT_PUBLIC_INSTITUTION,
    ),
    TargetRule(
        _pattern(r"\bparliament\b|\blok sabha\b|\brajya sabha\b|संसद|लोकसभा|राज्यसभा"),
        "Parliament of India",
        ActorType.COURT_PUBLIC_INSTITUTION,
    ),
    TargetRule(_pattern(r"\bbjp\b|भारतीय जनता पार्टी|भाजपा"), "Bharatiya Janata Party (BJP)", ActorType.RULING_PARTY),
    TargetRule(_pattern(r"\bcongress\b|कांग्रेस"), "Indian National Congress", ActorType.OPPOSITION_PARTY),
    TargetRule(_pattern(r"\bopposition\b|विपक्ष"), "Opposition parties", ActorType.OPPOSITION_PARTY),
    TargetRule(
        _pattern(r"\bparents?\b|अभिभावक|माता[- ]?पिता"),
        "Parents of NEET candidates",
        ActorType.PARENT,
    ),
    TargetRule(
        _pattern(r"\bstudents?\b|\bcandidates?\b|\baspirants?\b|\btoppers?\b|छात्र|अभ्यर्थी|उम्मीदवार"),
        "NEET candidates and students",
        ActorType.STUDENT_CANDIDATE,
    ),
    TargetRule(
        _pattern(r"\bprotests?\b|\bprotesters?\b|\bdemonstration\b|\bmarch\b|\bhunger strike\b|विरोध|प्रदर्शन|धरना|मार्च|भूख हड़ताल"),
        "NEET protest organisers and participants",
        ActorType.PROTEST_ORGANISER,
    ),
)


TOPIC_RULES: tuple[tuple[TopicLabel, re.Pattern[str]], ...] = (
    (TopicLabel.PROTEST_DEMANDS, _pattern(r"protest|demand|march|demonstration|hunger strike|विरोध|मांग|प्रदर्शन|धरना|मार्च|भूख हड़ताल")),
    (TopicLabel.STUDENT_CANDIDATE_EXPERIENCE, _pattern(r"student|candidate|aspirant|topper|score|छात्र|अभ्यर्थी|उम्मीदवार|टॉपर|अंक")),
    (TopicLabel.PARENT_RESPONSE, _pattern(r"parent|guardian|अभिभावक|माता[- ]?पिता")),
    (TopicLabel.EXAMINATION_ADMINISTRATION, _pattern(r"exam|neet|paper leak|nta|result|score|परीक्षा|नीट|पेपर लीक|एनटीए|परिणाम")),
    (TopicLabel.GOVERNMENT_RESPONSE, _pattern(r"minister|ministry|government|centre|bill|resign|मंत्री|मंत्रालय|सरकार|केंद्र|विधेयक|इस्तीफा")),
    (TopicLabel.POLICING_PUBLIC_ORDER, _pattern(r"police|arrest|detain|lathi|public order|पुलिस|गिरफ्तार|हिरासत|लाठी")),
    (TopicLabel.PARTY_POLITICS, _pattern(r"bjp|congress|opposition|political|भाजपा|कांग्रेस|विपक्ष|राजनीतिक")),
    (TopicLabel.COURTS_LEGAL_PROCESS, _pattern(r"court|cji|pil|judicial|legal|hearing|अदालत|न्यायालय|याचिका|सुनवाई")),
    (TopicLabel.PUBLIC_DISRUPTION, _pattern(r"traffic|blockade|disruption|road block|यातायात|जाम|अवरोध")),
    (TopicLabel.EVIDENCE_VERIFICATION, _pattern(r"probe|investigation|cbi|evidence|verify|fact[- ]?check|जांच|सीबीआई|सबूत|सत्यापन")),
)


FRAME_RULES: tuple[tuple[FrameLabel, re.Pattern[str]], ...] = (
    (FrameLabel.LAW_AND_ORDER, _pattern(r"police|arrest|detain|violence|mob|anarchy|public order|पुलिस|गिरफ्तार|हिंसा|भीड़|अराजकता")),
    (FrameLabel.CIVIL_RIGHTS, _pattern(r"protest|march|demonstration|rights|excesses|विरोध|मार्च|प्रदर्शन|अधिकार|अत्याचार")),
    (FrameLabel.INSTITUTIONAL_ACCOUNTABILITY, _pattern(r"resign|failure|accountability|probe|investigation|paper leak|scam|इस्तीफा|विफलता|जवाबदेही|जांच|पेपर लीक|घोटाला")),
    (FrameLabel.PROCEDURAL_LEGAL, _pattern(r"court|cji|pil|judicial|legal|bill|hearing|अदालत|न्यायालय|याचिका|विधेयक|सुनवाई")),
    (FrameLabel.PUBLIC_DISRUPTION, _pattern(r"traffic|blockade|disruption|road block|यातायात|जाम|अवरोध")),
    (FrameLabel.ELECTORAL_POLITICAL, _pattern(r"bjp|congress|opposition|political pressure|भाजपा|कांग्रेस|विपक्ष|राजनीतिक दबाव")),
    (FrameLabel.HUMAN_INTEREST, _pattern(r"topper|student story|hunger strike|interview|टॉपर|छात्र|भूख हड़ताल|साक्षात्कार")),
    (FrameLabel.EVIDENCE_VERIFICATION, _pattern(r"probe|investigation|cbi|evidence|verify|fact[- ]?check|जांच|सीबीआई|सबूत|सत्यापन")),
    (FrameLabel.DELEGITIMISING, _pattern(r"anarchy|goonda|fake protest|mob|अराजकता|गुंडा|फर्जी प्रदर्शन|भीड़")),
    (FrameLabel.CRIMINALISING, _pattern(r"criminal|riot|mob|goonda|violent protesters|अपराधी|दंगा|गुंडा|हिंसक प्रदर्शनकारी")),
    (FrameLabel.LEGITIMISING, _pattern(r"backs? the protest|supports? the protest|solidarity|protest in support|समर्थन में|एकजुटता")),
)


LOADED_TERMS = (
    "anarchy",
    "goonda",
    "mob",
    "chaos",
    "violent protesters",
    "fake protest",
    "scam",
    "fraud",
    "brutality",
    "अराजकता",
    "गुंडा",
    "हिंसक प्रदर्शनकारी",
    "फर्जी प्रदर्शन",
    "घोटाला",
    "बर्बरता",
)


def extract_targets(title: str) -> list[TargetActor]:
    """Return explicitly signalled target actors in deterministic rule order."""
    targets: list[TargetActor] = []
    seen: set[tuple[str, ActorType]] = set()
    for rule in TARGET_RULES:
        if not rule.pattern.search(title):
            continue
        key = (rule.name, rule.actor_type)
        if key in seen:
            continue
        seen.add(key)
        targets.append(TargetActor(name=rule.name, actor_type=rule.actor_type))
    return targets[:6]


def classify_topics(title: str) -> list[TopicLabel]:
    labels = [label for label, pattern in TOPIC_RULES if pattern.search(title)]
    return labels or [TopicLabel.OTHER_RELEVANT]


def classify_frames(title: str) -> list[FrameLabel]:
    return [label for label, pattern in FRAME_RULES if pattern.search(title)]


def classify_claim(title: str) -> tuple[ClaimType, CertaintyTreatment, bool | None]:
    lowered = title.casefold()
    if "?" in title or re.search(r"^(why|how|will|is|can|did|क्या|क्यों|कैसे)\b", lowered):
        return ClaimType.QUESTION, CertaintyTreatment.UNCLEAR, None
    if re.search(r"alleged|allegation|claims?|accuses?|आरोप|दावा", lowered):
        return (
            ClaimType.REPORTED_ALLEGATION,
            CertaintyTreatment.EXPLICITLY_QUALIFIED,
            True,
        )
    if re.search(r"[\"“”]|\bsays?\b|\btells?\b|\baccording to\b|कहा|बताया", title, re.IGNORECASE):
        return ClaimType.QUOTATION, CertaintyTreatment.IMPLICITLY_QUALIFIED, None
    return ClaimType.OBSERVED_FACT, CertaintyTreatment.ASSERTED_AS_FACT, None


def classify_stance(title: str, target: TargetActor) -> StanceDirection:
    lowered = title.casefold()
    if "?" in title:
        return StanceDirection.UNCLEAR

    if target.actor_type in {ActorType.PROTEST_ORGANISER, ActorType.STUDENT_CANDIDATE}:
        if re.search(r"support|backs?|solidarity|in favour|समर्थन|एकजुटता", lowered):
            return StanceDirection.FAVOURABLE
        if re.search(r"anarchy|goonda|fake protest|mob|violent protesters|अराजकता|गुंडा|फर्जी प्रदर्शन|हिंसक प्रदर्शनकारी", lowered):
            return StanceDirection.CRITICAL

    if target.actor_type is ActorType.POLICE:
        if re.search(r"excesses|brutality|crackdown|lathi|अत्याचार|बर्बरता|लाठीचार्ज", lowered):
            return StanceDirection.CRITICAL

    if target.actor_type in {
        ActorType.GOVERNMENT_REPRESENTATIVE,
        ActorType.EDUCATION_EXAM_AUTHORITY,
        ActorType.RULING_PARTY,
        ActorType.OPPOSITION_PARTY,
    }:
        if re.search(r"resign|failure|blame|accus|scam|fraud|paper leak|इस्तीफा|विफलता|आरोप|घोटाला|पेपर लीक", lowered):
            return StanceDirection.CRITICAL
        if re.search(r"relief|reform|assures?|welcomes?|praises?|राहत|सुधार|आश्वासन|स्वागत|सराहना", lowered):
            return StanceDirection.FAVOURABLE

    return StanceDirection.NEUTRAL_DESCRIPTIVE


def loaded_language(title: str) -> list[LoadedLanguage]:
    lowered = title.casefold()
    records: list[LoadedLanguage] = []
    for term in LOADED_TERMS:
        if term.casefold() not in lowered:
            continue
        records.append(
            LoadedLanguage(
                term=term,
                rationale=(
                    "Evaluative descriptor in headline packaging; machine-flagged for "
                    "contextual review, not treated as a factual verdict."
                ),
            )
        )
    return records


def _record_id(source: SourceInventoryRecord, target: TargetActor) -> str:
    target_slug = re.sub(r"[^a-z0-9]+", "-", target.name.casefold()).strip("-")[:28]
    digest = sha256(
        f"{PIPELINE_VERSION}|{source.source_id}|{target.name}|{target.actor_type.value}".encode()
    ).hexdigest()[:12]
    source_fragment = source.source_id.removeprefix("src-")[:12]
    return f"{AUTOMATED_PREFIX}{source_fragment}-{target_slug}-{digest}"[:100]


def build_record(source: SourceInventoryRecord, target: TargetActor) -> EvidenceSegment:
    claim_type, certainty, allegation_qualified = classify_claim(source.title)
    return EvidenceSegment(
        schema_version="1.0.0",
        record_id=_record_id(source, target),
        source_url=source.source_url,
        outlet=source.outlet,
        programme=source.programme,
        title=source.title,
        published_at=source.published_at,
        accessed_at=source.accessed_at,
        evidence_kind=EvidenceKind.HEADLINE,
        segment_start_seconds=0.0,
        segment_end_seconds=1.0,
        speaker=Speaker(
            name=source.outlet,
            role=SpeakerRole.INSTITUTIONAL_STATEMENT,
            affiliation=source.outlet,
            represented_actor_type=None,
        ),
        attributed_sources=[],
        target_actor=target,
        topic_labels=classify_topics(source.title),
        excerpt=source.title,
        original_language=source.original_language,
        translation=None,
        stance=classify_stance(source.title, target),
        frame_labels=classify_frames(source.title),
        loaded_language=loaded_language(source.title),
        claim_type=claim_type,
        certainty=certainty,
        allegation_qualified=allegation_qualified,
        packaging_support=PackagingSupport.NOT_REVIEWED,
        evidence_tier=EvidenceTier.C,
        transcript_sha256=None,
        review_status=ReviewStatus.MACHINE_ONLY,
        reviewed_at=None,
        reviewer_ids=[],
        context_notes=(
            "Machine-generated from accepted inventory headline metadata only. No article "
            "body, transcript, audio, video, or factual verification was reviewed. The "
            "0-1 second interval is a schema placeholder for packaging evidence, not media "
            "duration. This exploratory record is excluded from default published analytics."
        ),
    )


def _read_existing(path: Path) -> list[EvidenceSegment]:
    if not path.exists():
        return []
    records: list[EvidenceSegment] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            records.append(EvidenceSegment.model_validate_json(raw))
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return records


def _write_jsonl(path: Path, records: list[EvidenceSegment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        records,
        key=lambda item: (
            item.published_at.isoformat() if item.published_at else "",
            item.outlet.casefold(),
            str(item.source_url),
            item.record_id,
        ),
    )
    content = "\n".join(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        for record in ordered
    )
    path.write_text(f"{content}\n" if content else "", encoding="utf-8")


def _update_manifest(path: Path, record_count: int) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["record_count"] = record_count
    note = (
        " Machine-only headline packaging records are generated automatically and remain "
        "excluded from default published analytics until reviewed."
    )
    if note.strip() not in payload["notes"]:
        payload["notes"] = f"{payload['notes'].rstrip()}{note}"
    path.write_text(
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def generate(
    *,
    inventory_path: Path,
    data_path: Path,
    manifest_path: Path,
    report_path: Path,
    as_of: date,
    limit: int = 0,
) -> dict[str, Any]:
    inventory, errors = read_inventory(inventory_path)
    if errors:
        raise ValueError("\n".join(errors))

    candidates = [
        item
        for item in inventory
        if item.eligibility is EligibilityStatus.INCLUDED
        and item.availability is AvailabilityStatus.AVAILABLE
        and item.published_at is not None
        and item.published_at.date() <= as_of
    ]
    candidates.sort(
        key=lambda item: (
            item.published_at.isoformat() if item.published_at else "",
            item.outlet.casefold(),
            item.source_id,
        )
    )
    if limit > 0:
        candidates = candidates[:limit]

    existing = _read_existing(data_path)
    preserved = [
        record
        for record in existing
        if not (
            record.record_id.startswith(AUTOMATED_PREFIX)
            and record.review_status is ReviewStatus.MACHINE_ONLY
        )
    ]

    generated: list[EvidenceSegment] = []
    skipped_no_target: list[str] = []
    source_ids_with_records: set[str] = set()
    for source in candidates:
        targets = extract_targets(source.title)
        if not targets:
            skipped_no_target.append(source.source_id)
            continue
        source_ids_with_records.add(source.source_id)
        generated.extend(build_record(source, target) for target in targets)

    combined = preserved + generated
    record_ids = [record.record_id for record in combined]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("generated evidence contains duplicate record_id values")

    _write_jsonl(data_path, combined)
    _update_manifest(manifest_path, len(combined))

    report: dict[str, Any] = {
        "automated_evidence_version": PIPELINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_through": as_of.isoformat(),
        "mode": "headline_packaging_metadata_only",
        "inventory_source_count": len(inventory),
        "candidate_source_count": len(candidates),
        "source_count_with_generated_records": len(source_ids_with_records),
        "generated_record_count": len(generated),
        "preserved_non_automated_record_count": len(preserved),
        "total_evidence_record_count": len(combined),
        "skipped_no_explicit_target_count": len(skipped_no_target),
        "skipped_no_explicit_target_source_ids": skipped_no_target,
        "by_language": dict(
            sorted(Counter(record.original_language for record in generated).items())
        ),
        "by_stance": dict(sorted(Counter(record.stance.value for record in generated).items())),
        "by_target_actor_type": dict(
            sorted(Counter(record.target_actor.actor_type.value for record in generated).items())
        ),
        "by_topic": dict(
            sorted(Counter(label.value for record in generated for label in record.topic_labels).items())
        ),
        "limitations": [
            "Only accepted, available inventory metadata is used.",
            "No page body, transcript, audio, video, thumbnail image, or factual claim is reviewed.",
            "Target extraction and labels use deterministic lexical rules and can be wrong.",
            "All generated records remain machine_only and are excluded from default analytics.",
            "The packaging interval is a schema placeholder and does not represent media duration.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"{json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate conservative machine-only headline packaging evidence."
    )
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum included sources to process; zero processes every eligible source.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        report = generate(
            inventory_path=args.inventory,
            data_path=args.data,
            manifest_path=args.manifest,
            report_path=args.report,
            as_of=args.as_of,
            limit=args.limit,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(
        "Generated "
        f"{report['generated_record_count']} machine-only headline record(s) from "
        f"{report['source_count_with_generated_records']} source(s)."
    )


if __name__ == "__main__":
    main()
