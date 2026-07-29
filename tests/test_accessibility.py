from pathlib import Path

from src.accessibility import audit_html, audit_html_text
from src.analytics import AnalysisProvenance, build_summary
from src.reporting import render_report


def test_generated_report_passes_structural_accessibility_audit(tmp_path: Path) -> None:
    summary = build_summary(
        [],
        provenance=AnalysisProvenance(
            dataset_version="0.1.0",
            methodology_version="1.0.0",
            taxonomy_version="1.0.0",
            schema_version="1.0.0",
            evidence_sha256="a" * 64,
            correction_count=0,
            report_start="2026-07-01",
            report_through="2026-07-29",
            collection_end=None,
        ),
    )
    path = tmp_path / "report.html"
    path.write_text(render_report(summary), encoding="utf-8")

    report = audit_html(path)

    assert report["passed"] is True
    assert all(check["passed"] for check in report["checks"])


def test_audit_reports_actionable_structural_failures() -> None:
    report = audit_html_text(
        "<html><head><title></title><script src='https://example.test/a.js'></script>"
        "</head><body><main></main><main><h1>One</h1><h1>Two</h1>"
        "<label for='other'>Query</label><input id='query'><div id='same'></div>"
        "<div id='same'></div><img src='local.png'></body></html>"
    )
    failed = {check["name"] for check in report["checks"] if not check["passed"]}

    assert report["passed"] is False
    assert {
        "document_language",
        "document_title",
        "single_main",
        "single_h1",
        "unique_ids",
        "labelled_controls",
        "image_alternatives",
        "self_contained",
    } <= failed
