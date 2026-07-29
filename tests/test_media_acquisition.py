from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.inventory import (
    AvailabilityStatus,
    EligibilityStatus,
    MediaFormat,
    SourceInventoryRecord,
)
from src.media_acquisition import (
    acquire_source,
    audio_command,
    subtitle_command,
)


def _source() -> SourceInventoryRecord:
    return SourceInventoryRecord(
        inventory_version="1.0.0",
        source_id="src-testvideo001",
        source_url="https://example.com/video",
        outlet="Example News",
        programme=None,
        title="NEET protest video",
        published_at=datetime.fromisoformat("2026-07-10T10:00:00+05:30"),
        accessed_at=datetime.fromisoformat("2026-07-29T10:00:00+05:30"),
        original_language="en",
        media_format=MediaFormat.DIGITAL_VIDEO,
        availability=AvailabilityStatus.AVAILABLE,
        eligibility=EligibilityStatus.INCLUDED,
        discovery_method="unit test",
        discovery_query=None,
        exclusion_reason=None,
        eligible_segment_start_seconds=None,
        eligible_segment_end_seconds=None,
        notes=None,
    )


def test_subtitle_command_never_downloads_media(tmp_path: Path) -> None:
    command = subtitle_command(
        _source(),
        private_root=tmp_path,
        timeout=10,
        cookies_from_browser=None,
    )
    assert "--skip-download" in command
    assert "--write-auto-subs" in command
    assert "--write-subs" in command
    assert "bestaudio/best" not in command
    assert command[-1] == "https://example.com/video"


def test_audio_command_is_explicit_and_bounded(tmp_path: Path) -> None:
    command = audio_command(
        _source(),
        private_root=tmp_path,
        timeout=10,
        cookies_from_browser="chrome",
    )
    assert "bestaudio/best" in command
    assert "--max-filesize" in command
    assert "500M" in command
    assert "--cookies-from-browser" in command
    assert command[-1] == "https://example.com/video"


def test_existing_private_caption_prevents_network_acquisition(tmp_path: Path) -> None:
    transcript_root = tmp_path / "transcripts"
    transcript_root.mkdir(parents=True)
    caption = transcript_root / "src-testvideo001.vtt"
    caption.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nStudents protest NTA.\n",
        encoding="utf-8",
    )
    result = acquire_source(
        _source(),
        private_root=tmp_path,
        timeout=1,
        download_audio=False,
        cookies_from_browser=None,
    )
    assert result.status == "existing"
    assert result.method == "private_workspace"
    assert result.path == str(caption)
