from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.inventory import MediaFormat
from src.models import EvidenceKind, EvidenceSegment, EvidenceTier, ReviewStatus
from src.transcript_evidence import (
    build_windows,
    extract_youtube_id,
    generate,
    parse_vtt_or_srt,
)


def _write_inventory(path: Path, *, source_id: str = "src-testvideo001") -> None:
    payload = {
        "inventory_version": "1.0.0",
        "source_id": source_id,
        "source_url": "https://example.com/video",
        "outlet": "Example News",
        "programme": "Example Bulletin",
        "title": "NEET protest report",
        "published_at": "2026-07-10T10:00:00+05:30",
        "accessed_at": "2026-07-29T10:00:00+05:30",
        "original_language": "en",
        "media_format": "digital_video",
        "availability": "available",
        "eligibility": "included",
        "discovery_method": "unit test",
        "discovery_query": None,
        "exclusion_reason": None,
        "eligible_segment_start_seconds": None,
        "eligible_segment_end_seconds": None,
        "notes": None,
    }
    path.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")


def _write_manifest(path: Path) -> None:
    payload = {
        "project": "Project Parallax",
        "repository": "neet-protest-2026-media-analysis",
        "dataset": "NEET Protest 2026 Media Analysis",
        "dataset_version": "0.1.0",
        "methodology_version": "1.0.0",
        "taxonomy_version": "1.0.0",
        "schema_version": "1.0.0",
        "status": "collection",
        "collection_start": "2026-07-01",
        "collection_end": None,
        "included_event": "NEET 2026 protests",
        "record_count": 0,
        "generated_at": None,
        "notes": "Rolling collection.",
    }
    path.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")


def test_extract_youtube_id_supports_common_url_shapes() -> None:
    assert extract_youtube_id("https://www.youtube.com/watch?v=abc123XYZ_-") == "abc123XYZ_-"
    assert extract_youtube_id("https://youtu.be/abc123XYZ_-?si=test") == "abc123XYZ_-"
    assert extract_youtube_id("https://youtube.com/shorts/abc123XYZ_-") == "abc123XYZ_-"
    assert extract_youtube_id("https://example.com/watch?v=abc123XYZ_-") is None


def test_parse_vtt_and_group_windows() -> None:
    cues = parse_vtt_or_srt(
        """WEBVTT

00:00:00.000 --> 00:00:04.000
Students protested against NTA.

00:00:04.200 --> 00:00:09.000
They demanded accountability from the education ministry.
"""
    )
    assert len(cues) == 2
    windows = build_windows(tuple(cues))
    assert len(windows) == 1
    assert windows[0].start == 0
    assert windows[0].end == 9
    assert "education ministry" in windows[0].text


def test_generate_local_transcript_is_valid_and_idempotent(tmp_path: Path) -> None:
    inventory = tmp_path / "source-inventory.jsonl"
    data = tmp_path / "evidence-segments.jsonl"
    manifest = tmp_path / "collection-manifest.json"
    private_root = tmp_path / "private-workspace" / "transcripts"
    report = tmp_path / "transcript-report.json"
    private_root.mkdir(parents=True)
    data.write_text("", encoding="utf-8")
    _write_inventory(inventory)
    _write_manifest(manifest)
    (private_root / "src-testvideo001.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "start": 0,
                        "end": 8,
                        "text": "Students say NTA failed them and demand accountability.",
                    }
                ),
                json.dumps(
                    {
                        "start": 8,
                        "end": 17,
                        "text": "The NEET protest asked the education minister to resign.",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = generate(
        inventory_path=inventory,
        data_path=data,
        manifest_path=manifest,
        private_root=private_root,
        report_path=report,
        as_of=date(2026, 7, 29),
        allow_network=False,
        timeout=1,
        limit=0,
        media_formats={MediaFormat.DIGITAL_VIDEO},
        asr=None,
    )
    records = [
        EvidenceSegment.model_validate_json(line)
        for line in data.read_text(encoding="utf-8").splitlines()
    ]
    assert first["acquired_source_count"] == 1
    assert first["source_count_with_generated_records"] == 1
    assert first["generated_record_count"] == len(records)
    assert len(records) >= 2
    assert all(record.evidence_kind is EvidenceKind.SPOKEN for record in records)
    assert all(record.evidence_tier is EvidenceTier.D for record in records)
    assert all(record.review_status is ReviewStatus.MACHINE_ONLY for record in records)
    assert all(record.transcript_sha256 for record in records)
    assert all(record.segment_end_seconds > record.segment_start_seconds for record in records)
    assert json.loads(manifest.read_text(encoding="utf-8"))["record_count"] == len(records)

    second = generate(
        inventory_path=inventory,
        data_path=data,
        manifest_path=manifest,
        private_root=private_root,
        report_path=report,
        as_of=date(2026, 7, 29),
        allow_network=False,
        timeout=1,
        limit=0,
        media_formats={MediaFormat.DIGITAL_VIDEO},
        asr=None,
    )
    rerun_ids = [
        json.loads(line)["record_id"]
        for line in data.read_text(encoding="utf-8").splitlines()
    ]
    assert second["generated_record_count"] == first["generated_record_count"]
    assert len(rerun_ids) == len(set(rerun_ids)) == len(records)


def test_missing_transcript_is_reported_without_invalid_records(tmp_path: Path) -> None:
    inventory = tmp_path / "source-inventory.jsonl"
    data = tmp_path / "evidence-segments.jsonl"
    manifest = tmp_path / "collection-manifest.json"
    private_root = tmp_path / "private-workspace" / "transcripts"
    report = tmp_path / "transcript-report.json"
    private_root.mkdir(parents=True)
    data.write_text("", encoding="utf-8")
    _write_inventory(inventory)
    _write_manifest(manifest)

    result = generate(
        inventory_path=inventory,
        data_path=data,
        manifest_path=manifest,
        private_root=private_root,
        report_path=report,
        as_of=date(2026, 7, 29),
        allow_network=False,
        timeout=1,
        limit=0,
        media_formats={MediaFormat.DIGITAL_VIDEO},
        asr=None,
    )
    assert result["failed_source_count"] == 1
    assert result["generated_record_count"] == 0
    assert data.read_text(encoding="utf-8") == ""
    assert json.loads(manifest.read_text(encoding="utf-8"))["record_count"] == 0
