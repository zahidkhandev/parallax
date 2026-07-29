"""Acquire captions or audio into the private workspace for local transcription.

This command is intentionally designed for a user-controlled self-hosted runner. It
never writes third-party media or complete captions to public Git paths.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .inventory import (
    AvailabilityStatus,
    EligibilityStatus,
    MediaFormat,
    SourceInventoryRecord,
    read_inventory,
)

DEFAULT_INVENTORY = Path("public-data/source-inventory.jsonl")
DEFAULT_PRIVATE_ROOT = Path("private-workspace")
DEFAULT_REPORT = Path("build/media-acquisition-report.json")
PIPELINE_VERSION = "1.0.0"
SUPPORTED_MEDIA_FORMATS = {
    MediaFormat.TV_REPORT,
    MediaFormat.TV_DEBATE,
    MediaFormat.DIGITAL_VIDEO,
    MediaFormat.INTERVIEW,
    MediaFormat.LIVE_STREAM,
    MediaFormat.ARTICLE_WITH_VIDEO,
}
CAPTION_EXTENSIONS = (".vtt", ".srt", ".jsonl", ".json")
MEDIA_EXTENSIONS = (".wav", ".mp3", ".m4a", ".mp4", ".webm", ".mkv", ".mov", ".ogg", ".flac")


@dataclass(frozen=True)
class AcquisitionResult:
    source_id: str
    source_url: str
    status: str
    method: str | None
    path: str | None
    reason: str | None


def _existing_file(root: Path, source_id: str) -> Path | None:
    transcript_root = root / "transcripts"
    media_root = root / "media"
    for suffix in CAPTION_EXTENSIONS:
        path = transcript_root / f"{source_id}{suffix}"
        if path.exists():
            return path
    for suffix in MEDIA_EXTENSIONS:
        path = media_root / f"{source_id}{suffix}"
        if path.exists():
            return path
    return None


def subtitle_command(
    source: SourceInventoryRecord,
    *,
    private_root: Path,
    timeout: float,
    cookies_from_browser: str | None,
) -> list[str]:
    output = private_root / "transcripts" / f"{source.source_id}.%(language)s.%(ext)s"
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "hi.*,en.*",
        "--sub-format",
        "vtt",
        "--skip-download",
        "--restrict-filenames",
        "--no-warnings",
        "--socket-timeout",
        str(timeout),
        "--retries",
        "2",
        "-o",
        str(output),
    ]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(str(source.source_url))
    return command


def audio_command(
    source: SourceInventoryRecord,
    *,
    private_root: Path,
    timeout: float,
    cookies_from_browser: str | None,
) -> list[str]:
    output = private_root / "media" / f"{source.source_id}.%(ext)s"
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "-f",
        "bestaudio/best",
        "--max-filesize",
        "500M",
        "--restrict-filenames",
        "--no-warnings",
        "--socket-timeout",
        str(timeout),
        "--retries",
        "2",
        "-o",
        str(output),
    ]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(str(source.source_url))
    return command


def _run(command: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    detail = (completed.stderr or completed.stdout).strip()
    return completed.returncode == 0, detail[-1000:]


def _normalize_caption(private_root: Path, source_id: str) -> Path | None:
    transcript_root = private_root / "transcripts"
    candidates = sorted(
        [
            *transcript_root.glob(f"{source_id}*.vtt"),
            *transcript_root.glob(f"{source_id}*.srt"),
        ],
        key=lambda path: (
            0 if ".hi" in path.name.casefold() else 1,
            0 if ".en" in path.name.casefold() else 1,
            path.name,
        ),
    )
    if not candidates:
        return None
    source = candidates[0]
    target = transcript_root / f"{source_id}{source.suffix.casefold()}"
    if source != target:
        shutil.copyfile(source, target)
    return target


def _downloaded_media(private_root: Path, source_id: str) -> Path | None:
    media_root = private_root / "media"
    for suffix in MEDIA_EXTENSIONS:
        path = media_root / f"{source_id}{suffix}"
        if path.exists():
            return path
    matches = sorted(media_root.glob(f"{source_id}.*"))
    return matches[0] if matches else None


def acquire_source(
    source: SourceInventoryRecord,
    *,
    private_root: Path,
    timeout: float,
    download_audio: bool,
    cookies_from_browser: str | None,
) -> AcquisitionResult:
    existing = _existing_file(private_root, source.source_id)
    if existing:
        return AcquisitionResult(
            source_id=source.source_id,
            source_url=str(source.source_url),
            status="existing",
            method="private_workspace",
            path=str(existing),
            reason=None,
        )

    ok, subtitle_detail = _run(
        subtitle_command(
            source,
            private_root=private_root,
            timeout=timeout,
            cookies_from_browser=cookies_from_browser,
        )
    )
    caption = _normalize_caption(private_root, source.source_id)
    if ok and caption:
        return AcquisitionResult(
            source_id=source.source_id,
            source_url=str(source.source_url),
            status="acquired",
            method="yt_dlp_captions",
            path=str(caption),
            reason=None,
        )

    if not download_audio:
        reason = subtitle_detail or "no timed captions found"
        return AcquisitionResult(
            source_id=source.source_id,
            source_url=str(source.source_url),
            status="failed",
            method=None,
            path=None,
            reason=reason,
        )

    ok, audio_detail = _run(
        audio_command(
            source,
            private_root=private_root,
            timeout=timeout,
            cookies_from_browser=cookies_from_browser,
        )
    )
    media = _downloaded_media(private_root, source.source_id)
    if ok and media:
        return AcquisitionResult(
            source_id=source.source_id,
            source_url=str(source.source_url),
            status="acquired",
            method="yt_dlp_audio",
            path=str(media),
            reason=None,
        )
    reason = audio_detail or subtitle_detail or "media acquisition failed"
    return AcquisitionResult(
        source_id=source.source_id,
        source_url=str(source.source_url),
        status="failed",
        method=None,
        path=None,
        reason=reason,
    )


def acquire(
    *,
    inventory_path: Path,
    private_root: Path,
    report_path: Path,
    as_of: date,
    limit: int,
    source_ids: set[str],
    media_formats: set[MediaFormat],
    timeout: float,
    download_audio: bool,
    cookies_from_browser: str | None,
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
        and (not source_ids or item.source_id in source_ids)
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

    (private_root / "transcripts").mkdir(parents=True, exist_ok=True)
    (private_root / "media").mkdir(parents=True, exist_ok=True)
    results = [
        acquire_source(
            source,
            private_root=private_root,
            timeout=timeout,
            download_audio=download_audio,
            cookies_from_browser=cookies_from_browser,
        )
        for source in candidates
    ]
    status_counts = Counter(result.status for result in results)
    method_counts = Counter(result.method for result in results if result.method)
    report: dict[str, Any] = {
        "media_acquisition_version": PIPELINE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "report_through": as_of.isoformat(),
        "candidate_source_count": len(candidates),
        "download_audio_enabled": download_audio,
        "by_status": dict(sorted(status_counts.items())),
        "by_method": dict(sorted(method_counts.items())),
        "results": [
            {
                "source_id": result.source_id,
                "source_url": result.source_url,
                "status": result.status,
                "method": result.method,
                "private_path": result.path,
                "reason": result.reason,
            }
            for result in results
        ],
        "limitations": [
            "Run only on a user-controlled machine and only where acquisition is lawful.",
            "Publisher protections, authentication, geo-restrictions and site changes can fail.",
            "Third-party media and complete captions remain in the gitignored private workspace.",
            "Acquisition success does not establish transcript accuracy or speaker identity.",
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
        description="Acquire captions or audio into the private transcript workspace."
    )
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--download-audio", action="store_true")
    parser.add_argument("--cookies-from-browser")
    parser.add_argument("--source-id", action="append", dest="source_ids")
    parser.add_argument(
        "--media-format",
        action="append",
        choices=[item.value for item in MediaFormat],
        dest="media_formats",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    formats = (
        {MediaFormat(value) for value in args.media_formats}
        if args.media_formats
        else SUPPORTED_MEDIA_FORMATS
    )
    try:
        report = acquire(
            inventory_path=args.inventory,
            private_root=args.private_root,
            report_path=args.report,
            as_of=args.as_of,
            limit=args.limit,
            source_ids=set(args.source_ids or []),
            media_formats=formats,
            timeout=args.timeout,
            download_audio=args.download_audio,
            cookies_from_browser=args.cookies_from_browser,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(
        f"Processed {report['candidate_source_count']} source(s): "
        f"{report['by_status'].get('acquired', 0)} acquired, "
        f"{report['by_status'].get('existing', 0)} existing, "
        f"{report['by_status'].get('failed', 0)} failed."
    )


if __name__ == "__main__":
    main()
