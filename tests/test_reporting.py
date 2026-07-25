from copy import deepcopy

from src.analytics import AnalysisProvenance, build_summary
from src.models import CorrectionRecord, EvidenceSegment
from src.reporting import render_report
from tests.test_models import valid_record


def provenance() -> AnalysisProvenance:
    return AnalysisProvenance(
        dataset_version="0.1.0",
        methodology_version="1.0.0",
        taxonomy_version="1.0.0",
        schema_version="1.0.0",
        evidence_sha256="a" * 64,
        correction_count=1,
        report_start="2026-07-01",
        report_through="2026-07-25",
        collection_end=None,
    )


def test_report_renders_attribution_timestamp_filters_and_corrections() -> None:
    payload = deepcopy(valid_record())
    payload["published_at"] = "2026-07-20T09:00:00+05:30"
    payload["title"] = "A <script>alert('title')</script>"
    payload["excerpt"] = "Limited <b>evidence</b> excerpt."
    payload["target_actor"]["name"] = "Target <img src=x>"
    record = EvidenceSegment.model_validate(payload)
    correction = CorrectionRecord.model_validate(
        {
            "correction_id": "cor-example-001",
            "record_id": record.record_id,
            "corrected_at": "2026-07-24T10:00:00Z",
            "field": "target_actor.name",
            "original_value": "Old",
            "corrected_value": "New",
            "reason": "Reason <script>alert('reason')</script>",
            "reviewer": "reviewer-002",
            "metrics_affected": True,
        }
    )
    summary = build_summary([record], provenance=provenance())

    html = render_report(summary, [record], [correction])

    assert "Timestamped evidence explorer" in html
    assert "00:00:10–00:00:20" in html
    assert "Test speaker" in html
    assert "Target &lt;img src=x&gt;" in html
    assert "Limited &lt;b&gt;evidence&lt;/b&gt; excerpt." in html
    assert "A &lt;script&gt;alert(&#x27;title&#x27;)&lt;/script&gt;" in html
    assert "Reason &lt;script&gt;alert(&#x27;reason&#x27;)&lt;/script&gt;" in html
    assert "<script>alert('title')</script>" not in html
    assert "id=\"stance-filter\"" in html
    assert "cor-example-001" in html


def test_report_empty_state_is_explicit() -> None:
    summary = build_summary([], provenance=provenance())
    html = render_report(summary)
    assert "No reviewed evidence has been published" in html
    assert "No reviewed evidence records are available" in html
    assert "No corrections recorded" in html
