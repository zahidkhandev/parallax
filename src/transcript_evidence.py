"""Acquire timed transcripts and generate conservative machine-only spoken evidence.

The pipeline prefers locally supplied caption files, then publisher/YouTube captions,
and optionally a locally available Faster-Whisper model. Complete transcripts are
written only under the gitignored private workspace. Public output contains bounded
excerpts, timestamps, transcript hashes, and machine-only annotations.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from .automated_evidence import (
    classify_claim,
    classify_frames,
    classify_stance,
    classify_topics,
    extract_targets,
    loaded_language,
)
from .inventory import (
    AvailabilityStatus,
    EligibilityStatus,
    MediaFormat,
    SourceInventoryRecord,
    read_inventory,
)
from .models import (
    EvidenceKind,
    EvidenceSegment,
    EvidenceTier,
    PackagingSupport,
    ReviewStatus,
    Speaker,
    SpeakerRole,
    TargetActor,
)

DEFAULT_INVENTORY = Path("public-data/source-inventory.jsonl")
DEFAULT_DATA = Path("public-data/evidence-segments.jsonl")
DEFAULT_MANIFEST = Path("public-data/collection-manifest.json")
DEFAULT_PRIVATE_ROOT = Path("private-workspace/transcripts")
DEFAULT_REPORT = Path("build/transcript-evidence-report.json")
AUTOMATED_PREFIX = "auto-transcript-"
PIPELINE_VERSION = "1.0.0"
SUPPORTED_MEDIA_FORMATS = {
    MediaFormat.TV_REPORT,
    MediaFormat.TV_DEBATE,
    MediaFormat.DIGITAL_VIDEO,
    MediaFormat.INTERVIEW,
    MediaFormat.LIVE_STREAM,
    MediaFormat.ARTICLE_WITH_VIDEO,
}
MEDIA_EXTENSIONS = (".wav", ".mp3", ".m4a", ".mp4", ".webm", ".mkv", ".mov", ".ogg", ".flac")
TIMESTAMP = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})"
)
TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class TranscriptCue:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class TranscriptDocument:
    source_id: str
    language: str
    method: str
    cues: tuple[TranscriptCue, ...]
    sha256: str


@dataclass(frozen=True)
class EvidenceWindow:
    start: float
    end: float
    text: str
    speaker: str | None


class TrackParser(HTMLParser):
    """Collect timed-text tracks and embedded YouTube URLs from publisher HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.tracks: list[tuple[str, str | None]] = []
        self.youtube_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value for key, value in attrs}
        if tag.casefold() == "track":
            kind = (values.get("kind") or "").casefold()
            src = values.get("src")
            if src and kind in {"captions", "subtitles"}:
                self.tracks.append((src, values.get("srclang")))
        if tag.casefold() == "iframe":
            src = values.get("src")
            if src and extract_youtube_id(src):
                self.youtube_urls.append(src)


def _clean_text(value: str) -> str:
    value = TAG.sub("", html.unescape(value))
    return re.sub(r"\s+", " ", value).strip()


def _seconds(value: str) -> float:
    chunks = value.replace(",", ".").split(":")
    if len(chunks) == 2:
        minutes, seconds = chunks
        return float(minutes) * 60 + float(seconds)
    hours, minutes, seconds = chunks
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)


def parse_vtt_or_srt(content: str) -> list[TranscriptCue]:
    """Parse basic WebVTT or SubRip captions without retaining formatting."""
    lines = content.replace("\ufeff", "").splitlines()
    cues: list[TranscriptCue] = []
    index = 0
    while index < len(lines):
        match = TIMESTAMP.search(lines[index])
        if not match:
            index += 1
            continue
        start = _seconds(match.group("start"))
        end = _seconds(match.group("end"))
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1
        text = _clean_text(" ".join(text_lines))
        if text and end > start:
            cues.append(TranscriptCue(start=start, end=end, text=text))
        index += 1
    return cues


def parse_json_transcript(content: str) -> list[TranscriptCue]:
    payload = json.loads(content)
    items = payload.get("segments", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("JSON transcript must be a list or contain a segments list")
    cues: list[TranscriptCue] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = float(item.get("start", item.get("start_seconds", 0)))
        if "end" in item or "end_seconds" in item:
            end = float(item.get("end", item.get("end_seconds")))
        else:
            end = start + float(item.get("duration", 0))
        text = _clean_text(str(item.get("text", "")))
        speaker = _clean_text(str(item["speaker"])) if item.get("speaker") else None
        if text and end > start:
            cues.append(TranscriptCue(start=start, end=end, text=text, speaker=speaker))
    return cues


def parse_jsonl_transcript(content: str) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    for line_number, raw in enumerate(content.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid transcript JSONL at line {line_number}: {exc}") from exc
        cues.extend(parse_json_transcript(json.dumps([payload], ensure_ascii=False)))
    return cues


def extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.casefold().removeprefix("www.")
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            candidate = (
                parts[1]
                if len(parts) > 1 and parts[0] in {"embed", "shorts", "live"}
                else ""
            )
    else:
        return None
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", candidate) else None


def transcript_digest(cues: list[TranscriptCue]) -> str:
    normalized = "\n".join(
        f"{cue.start:.3f}|{cue.end:.3f}|{cue.speaker or ''}|{cue.text}" for cue in cues
    )
    return sha256(normalized.encode("utf-8")).hexdigest()


def _local_candidates(root: Path, source_id: str) -> list[Path]:
    paths = [root / f"{source_id}{suffix}" for suffix in (".jsonl", ".json", ".vtt", ".srt")]
    media_root = root.parent / "media"
    paths.extend(media_root / f"{source_id}{suffix}" for suffix in MEDIA_EXTENSIONS)
    return paths


def _parse_caption_path(path: Path) -> list[TranscriptCue]:
    content = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return parse_jsonl_transcript(content)
    if path.suffix == ".json":
        return parse_json_transcript(content)
    return parse_vtt_or_srt(content)


def _write_private_cache(root: Path, document: TranscriptDocument) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{document.source_id}.jsonl"
    content = "\n".join(
        json.dumps(
            {
                "start": cue.start,
                "end": cue.end,
                "text": cue.text,
                "speaker": cue.speaker,
                "language": document.language,
                "acquisition_method": document.method,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for cue in document.cues
    )
    path.write_text(f"{content}\n" if content else "", encoding="utf-8")


def _fetch_text(url: str, timeout: float) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Project-Parallax/1.0 (+https://github.com/zahidkhandev/parallax; "
                "research transcript metadata collector)"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        content_type = response.headers.get_content_type()
        return response.read().decode(charset, errors="replace"), content_type


def _youtube_transcript(video_id: str, languages: list[str]) -> tuple[list[TranscriptCue], str]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise RuntimeError(
            "youtube-transcript-api is not installed; install the transcripts extra"
        ) from exc

    transcript = YouTubeTranscriptApi().fetch(video_id, languages=languages)
    cues = [
        TranscriptCue(
            start=float(item.start),
            end=float(item.start + item.duration),
            text=_clean_text(item.text),
        )
        for item in transcript
        if _clean_text(item.text) and item.duration > 0
    ]
    language = getattr(transcript, "language_code", None) or languages[0]
    return cues, language


def _publisher_tracks(
    source: SourceInventoryRecord,
    *,
    timeout: float,
) -> tuple[list[TranscriptCue], str, str]:
    page, _ = _fetch_text(str(source.source_url), timeout)
    parser = TrackParser()
    parser.feed(page)
    preferred = [source.original_language.split("-")[0], "hi", "en"]

    for embedded_url in parser.youtube_urls:
        video_id = extract_youtube_id(embedded_url)
        if not video_id:
            continue
        cues, language = _youtube_transcript(video_id, preferred)
        if cues:
            return cues, language, "embedded_youtube_captions"

    ranked_tracks = sorted(
        parser.tracks,
        key=lambda item: (
            preferred.index(item[1]) if item[1] in preferred else len(preferred),
            item[0],
        ),
    )
    for track_url, language in ranked_tracks:
        absolute = urljoin(str(source.source_url), track_url)
        content, content_type = _fetch_text(absolute, timeout)
        if content_type not in {"text/vtt", "application/x-subrip", "text/plain"}:
            if not absolute.casefold().endswith((".vtt", ".srt")):
                continue
        cues = parse_vtt_or_srt(content)
        if cues:
            return cues, language or source.original_language, "publisher_caption_track"
    raise RuntimeError("no usable timed caption track found")


class AsrEngine:
    """Lazily load Faster-Whisper only when a local media file needs transcription."""

    def __init__(self, model_size: str, device: str, compute_type: str) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any | None = None

    def transcribe(self, path: Path, language: str) -> tuple[list[TranscriptCue], str]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed; install the asr extra"
            ) from exc
        if self._model is None:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        language_code = language.split("-")[0] if language else None
        segments, info = self._model.transcribe(
            str(path),
            language=language_code,
            beam_size=5,
            vad_filter=True,
            word_timestamps=False,
        )
        cues = [
            TranscriptCue(
                start=float(segment.start),
                end=float(segment.end),
                text=_clean_text(segment.text),
            )
            for segment in segments
            if _clean_text(segment.text) and segment.end > segment.start
        ]
        detected = getattr(info, "language", None) or language or "und"
        return cues, detected


def acquire_transcript(
    source: SourceInventoryRecord,
    *,
    private_root: Path,
    allow_network: bool,
    timeout: float,
    asr: AsrEngine | None,
) -> TranscriptDocument:
    for path in _local_candidates(private_root, source.source_id):
        if not path.exists():
            continue
        if path.suffix in {".jsonl", ".json", ".vtt", ".srt"}:
            cues = _parse_caption_path(path)
            method = f"local_{path.suffix.removeprefix('.')}_captions"
            language = source.original_language
        elif asr is not None:
            cues, language = asr.transcribe(path, source.original_language)
            method = "local_faster_whisper"
        else:
            continue
        if cues:
            document = TranscriptDocument(
                source_id=source.source_id,
                language=language,
                method=method,
                cues=tuple(cues),
                sha256=transcript_digest(cues),
            )
            _write_private_cache(private_root, document)
            return document

    if not allow_network:
        raise RuntimeError("no local transcript or enabled network caption source")

    video_id = extract_youtube_id(str(source.source_url))
    if video_id:
        cues, language = _youtube_transcript(
            video_id,
            [source.original_language.split("-")[0], "hi", "en"],
        )
        method = "youtube_captions"
    else:
        cues, language, method = _publisher_tracks(source, timeout=timeout)
    if not cues:
        raise RuntimeError("caption source returned no timed transcript cues")
    document = TranscriptDocument(
        source_id=source.source_id,
        language=language,
        method=method,
        cues=tuple(cues),
        sha256=transcript_digest(cues),
    )
    _write_private_cache(private_root, document)
    return document


def build_windows(
    cues: tuple[TranscriptCue, ...],
    *,
    max_chars: int = 420,
    max_duration: float = 45.0,
    max_gap: float = 4.0,
) -> list[EvidenceWindow]:
    """Group adjacent cues into bounded, context-preserving evidence windows."""
    windows: list[EvidenceWindow] = []
    current: list[TranscriptCue] = []

    def flush() -> None:
        if not current:
            return
        speakers = {cue.speaker for cue in current if cue.speaker}
        windows.append(
            EvidenceWindow(
                start=current[0].start,
                end=current[-1].end,
                text=_clean_text(" ".join(cue.text for cue in current)),
                speaker=next(iter(speakers)) if len(speakers) == 1 else None,
            )
        )
        current.clear()

    for cue in cues:
        proposed_text = _clean_text(" ".join([*(item.text for item in current), cue.text]))
        duration = cue.end - current[0].start if current else cue.end - cue.start
        gap = cue.start - current[-1].end if current else 0
        speaker_changed = bool(
            current
            and current[-1].speaker
            and cue.speaker
            and current[-1].speaker != cue.speaker
        )
        if current and (
            len(proposed_text) > max_chars
            or duration > max_duration
            or gap > max_gap
            or speaker_changed
        ):
            flush()
        current.append(cue)
    flush()
    return [window for window in windows if window.text and window.end > window.start]


def _record_id(
    source: SourceInventoryRecord,
    window: EvidenceWindow,
    target: TargetActor,
    transcript_hash: str,
) -> str:
    target_slug = re.sub(r"[^a-z0-9]+", "-", target.name.casefold()).strip("-")[:20]
    start_ms = int(round(window.start * 1000))
    digest = sha256(
        (
            f"{PIPELINE_VERSION}|{source.source_id}|{start_ms}|{window.end:.3f}|"
            f"{target.name}|{target.actor_type.value}|{transcript_hash}"
        ).encode()
    ).hexdigest()[:10]
    source_fragment = source.source_id.removeprefix("src-")[:10]
    return f"{AUTOMATED_PREFIX}{source_fragment}-{start_ms}-{target_slug}-{digest}"[:100]


def _excerpt(text: str) -> str:
    if len(text) <= 500:
        return text
    truncated = text[:497].rsplit(" ", 1)[0].rstrip()
    return f"{truncated}..."


def build_record(
    source: SourceInventoryRecord,
    document: TranscriptDocument,
    window: EvidenceWindow,
    target: TargetActor,
) -> EvidenceSegment:
    claim_type, certainty, allegation_qualified = classify_claim(window.text)
    return EvidenceSegment(
        schema_version="1.0.0",
        record_id=_record_id(source, window, target, document.sha256),
        source_url=source.source_url,
        outlet=source.outlet,
        programme=source.programme,
        title=source.title,
        published_at=source.published_at,
        accessed_at=datetime.now(UTC),
        evidence_kind=EvidenceKind.SPOKEN,
        segment_start_seconds=window.start,
        segment_end_seconds=window.end,
        speaker=Speaker(
            name=window.speaker,
            role=SpeakerRole.UNKNOWN,
            affiliation=None,
            represented_actor_type=None,
        ),
        attributed_sources=[],
        target_actor=target,
        topic_labels=classify_topics(window.text),
        excerpt=_excerpt(window.text),
        original_language=document.language.split("-")[0],
        translation=None,
        stance=classify_stance(window.text, target),
        frame_labels=classify_frames(window.text),
        loaded_language=loaded_language(window.text),
        claim_type=claim_type,
        certainty=certainty,
        allegation_qualified=allegation_qualified,
        packaging_support=PackagingSupport.NOT_APPLICABLE,
        evidence_tier=EvidenceTier.D,
        transcript_sha256=document.sha256,
        review_status=ReviewStatus.MACHINE_ONLY,
        reviewed_at=None,
        reviewer_ids=[],
        context_notes=(
            f"Machine-generated from timed transcript cues acquired via {document.method}. "
            "The transcript, timestamps, speaker identity, translation, target and labels have "
            "not been human verified. Tier D is used because automated caption or ASR evidence "
            "does not establish verified speaker attribution. Complete transcript content is "
            "kept only in the gitignored private workspace."
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
    ordered = sorted(
        records,
        key=lambda item: (
            item.published_at.isoformat() if item.published_at else "",
            item.outlet.casefold(),
            str(item.source_url),
            item.segment_start_seconds,
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
        " Machine-only timed transcript records may be generated automatically; complete "
        "transcripts remain private and these records stay excluded from default analytics."
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
    private_root: Path,
    report_path: Path,
    as_of: date,
    allow_network: bool,
    timeout: float,
    limit: int,
    media_formats: set[MediaFormat],
    asr: AsrEngine | None,
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
        and item.media_format in media_formats
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
    failures: list[dict[str, str]] = []
    skipped_no_target: list[str] = []
    acquired_methods: Counter[str] = Counter()
    acquired_languages: Counter[str] = Counter()
    sources_with_records: set[str] = set()

    for source in candidates:
        try:
            document = acquire_transcript(
                source,
                private_root=private_root,
                allow_network=allow_network,
                timeout=timeout,
                asr=asr,
            )
        except Exception as exc:
            failures.append(
                {
                    "source_id": source.source_id,
                    "source_url": str(source.source_url),
                    "reason": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            )
            continue

        acquired_methods[document.method] += 1
        acquired_languages[document.language] += 1
        source_generated = 0
        for window in build_windows(document.cues):
            targets = extract_targets(window.text)
            if not targets:
                continue
            records = [
                build_record(source, document, window, target) for target in targets
            ]
            generated.extend(records)
            source_generated += len(records)
        if source_generated:
            sources_with_records.add(source.source_id)
        else:
            skipped_no_target.append(source.source_id)

    combined = preserved + generated
    record_ids = [record.record_id for record in combined]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("generated transcript evidence contains duplicate record_id values")
    _write_jsonl(data_path, combined)
    _update_manifest(manifest_path, len(combined))

    report: dict[str, Any] = {
        "transcript_evidence_version": PIPELINE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "report_through": as_of.isoformat(),
        "candidate_source_count": len(candidates),
        "acquired_source_count": sum(acquired_methods.values()),
        "source_count_with_generated_records": len(sources_with_records),
        "generated_record_count": len(generated),
        "preserved_record_count": len(preserved),
        "total_evidence_record_count": len(combined),
        "failed_source_count": len(failures),
        "failures": failures,
        "skipped_no_explicit_target_count": len(skipped_no_target),
        "skipped_no_explicit_target_source_ids": skipped_no_target,
        "by_acquisition_method": dict(sorted(acquired_methods.items())),
        "by_transcript_language": dict(sorted(acquired_languages.items())),
        "by_stance": dict(
            sorted(Counter(record.stance.value for record in generated).items())
        ),
        "by_target_actor_type": dict(
            sorted(
                Counter(
                    record.target_actor.actor_type.value for record in generated
                ).items()
            )
        ),
        "limitations": [
            "Automated captions and ASR can contain omissions, hallucinations and timing errors.",
            "Speaker diarisation and identity are not verified; generated evidence uses Tier D.",
            "Rules can misidentify targets, quotation boundaries, stance, topics and frames.",
            "Only short excerpts and transcript hashes are public; complete transcripts "
            "stay private.",
            "Every generated record remains machine_only and is excluded from default analytics.",
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
        description="Acquire timed transcripts and generate machine-only spoken evidence."
    )
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--media-format",
        action="append",
        choices=[item.value for item in MediaFormat],
        dest="media_formats",
    )
    parser.add_argument("--local-asr", action="store_true")
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--whisper-device", default="cpu")
    parser.add_argument("--whisper-compute-type", default="int8")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    formats = (
        {MediaFormat(value) for value in args.media_formats}
        if args.media_formats
        else SUPPORTED_MEDIA_FORMATS
    )
    asr = (
        AsrEngine(
            args.whisper_model,
            args.whisper_device,
            args.whisper_compute_type,
        )
        if args.local_asr
        else None
    )
    try:
        report = generate(
            inventory_path=args.inventory,
            data_path=args.data,
            manifest_path=args.manifest,
            private_root=args.private_root,
            report_path=args.report,
            as_of=args.as_of,
            allow_network=args.network,
            timeout=args.timeout,
            limit=args.limit,
            media_formats=formats,
            asr=asr,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(
        "Generated "
        f"{report['generated_record_count']} machine-only transcript record(s) from "
        f"{report['source_count_with_generated_records']} source(s); "
        f"{report['failed_source_count']} source(s) failed acquisition."
    )


if __name__ == "__main__":
    main()
