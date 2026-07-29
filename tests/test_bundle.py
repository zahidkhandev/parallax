import hashlib
import json
from pathlib import Path

from src.cli import run


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_draft_bundle_is_public_only_checksummed_and_reproducible(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    command = [
        "bundle",
        "--as-of",
        "2026-07-29",
        "--output",
        str(output),
        "--draft",
    ]
    assert run(command) == 0
    first = tree_bytes(output)
    manifest = json.loads(first["bundle-manifest.json"])
    assert manifest["draft"] is True
    assert manifest["ready"] is False
    assert "artifacts/report.html" in first
    assert "artifacts/metrics.json" in first
    assert "public-data/evidence-segments.jsonl" in first
    assert not any("private-workspace" in name for name in first)
    assert not any(name.endswith((".mp4", ".mp3", ".srt", ".vtt")) for name in first)
    for relative, expected in manifest["sha256"].items():
        assert hashlib.sha256(first[relative]).hexdigest() == expected

    assert run(command) == 0
    assert tree_bytes(output) == first


def test_strict_bundle_refuses_current_not_ready_collection(tmp_path: Path) -> None:
    output = tmp_path / "release"
    assert run(["bundle", "--as-of", "2026-07-29", "--output", str(output)]) == 1
    assert not output.exists()
