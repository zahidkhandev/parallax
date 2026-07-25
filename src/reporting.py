# ruff: noqa: E501
"""Accessible standalone HTML reporting for validated analytical summaries."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape
from typing import Any

from .analysis_models import AnalysisSummary
from .analytics import AnalysisOptions, include_record
from .models import CorrectionRecord, EvidenceSegment


def _bar_table(title: str, values: dict[str, int | float], unit: str = "records") -> str:
    maximum = max(values.values(), default=0)
    rows = []
    for label, value in sorted(values.items(), key=lambda item: (-item[1], item[0])):
        width = (float(value) / float(maximum) * 100) if maximum else 0
        rows.append(
            "<tr><th scope='row'>"
            f"{escape(label.replace('_', ' ').title())}</th><td>{value:g} {escape(unit)}</td>"
            f"<td class='bar-cell'><span style='width:{width:.2f}%'></span></td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='3' class='empty'>No included evidence yet.</td></tr>")
    return (
        f"<section><h2>{escape(title)}</h2><table><thead><tr><th>Category</th>"
        f"<th>{escape(unit.title())}</th><th>Relative magnitude</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def _stance_rows(summary: AnalysisSummary) -> str:
    rows = []
    for target, stances in sorted(summary.stance_by_target_type.items()):
        for stance, count in sorted(stances.items()):
            rows.append(
                f"<tr><th scope='row'>{escape(target.replace('_', ' ').title())}</th>"
                f"<td>{escape(stance.replace('_', ' '))}</td><td>{count}</td></tr>"
            )
    if not rows:
        rows.append("<tr><td colspan='3' class='empty'>No reviewed stance records yet.</td></tr>")
    return "".join(rows)


def _timestamp(seconds: float) -> str:
    whole = int(seconds)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _evidence_explorer(records: Iterable[EvidenceSegment]) -> str:
    rows = []
    for record in records:
        speaker = record.speaker.name or record.speaker.role.value.replace("_", " ")
        excerpt = record.translation or record.excerpt
        search = " ".join(
            (
                record.outlet,
                speaker,
                record.target_actor.name,
                record.target_actor.actor_type.value,
                record.stance.value,
                excerpt,
            )
        ).casefold()
        rows.append(
            f"<tr class='evidence-row' data-search='{escape(search, quote=True)}' "
            f"data-stance='{escape(record.stance.value, quote=True)}' "
            f"data-tier='{escape(record.evidence_tier.value, quote=True)}' "
            f"data-review='{escape(record.review_status.value, quote=True)}'>"
            f"<td><a href='{escape(str(record.source_url), quote=True)}' rel='noopener noreferrer'>"
            f"{escape(record.outlet)}</a><br><small>{escape(record.title)}</small></td>"
            f"<td>{_timestamp(record.segment_start_seconds)}–{_timestamp(record.segment_end_seconds)}</td>"
            f"<td>{escape(speaker)}<br><small>{escape(record.speaker.role.value.replace('_', ' '))}</small></td>"
            f"<td>{escape(record.target_actor.name)}<br><small>{escape(record.target_actor.actor_type.value.replace('_', ' '))}</small></td>"
            f"<td>{escape(record.stance.value.replace('_', ' '))}</td>"
            f"<td><q>{escape(excerpt)}</q></td>"
            f"<td>{escape(record.evidence_tier.value)} / {escape(record.review_status.value.replace('_', ' '))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append(
            "<tr class='empty-row'><td colspan='7' class='empty'>"
            "No reviewed evidence records are available for this report window.</td></tr>"
        )
    return "".join(rows)


def _correction_rows(corrections: Iterable[CorrectionRecord]) -> str:
    rows = []
    for item in corrections:
        rows.append(
            f"<tr><th scope='row'>{escape(item.correction_id)}</th>"
            f"<td>{escape(item.record_id)}</td><td>{escape(item.field)}</td>"
            f"<td>{escape(item.corrected_at.isoformat())}</td><td>{escape(item.reason)}</td>"
            f"<td>{'yes' if item.metrics_affected else 'no'}</td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='6' class='empty'>No corrections recorded.</td></tr>")
    return "".join(rows)


def render_report(
    payload: dict[str, Any],
    records: Iterable[EvidenceSegment] = (),
    corrections: Iterable[CorrectionRecord] = (),
) -> str:
    summary = AnalysisSummary.model_validate(payload)
    provenance = summary.provenance
    if provenance is None:
        raise ValueError("report generation requires analysis provenance")
    population = summary.population
    options = AnalysisOptions(
        summary.options.include_machine_only, summary.options.include_rejected
    )
    visible_records = [record for record in records if include_record(record, options)]
    review_percent = (
        f"{population.human_review_coverage * 100:.1f}%"
        if population.human_review_coverage is not None
        else "Not available"
    )
    window = f"{provenance.report_start:%d %b %Y} through {provenance.report_through:%d %b %Y}"
    status = (
        "No reviewed evidence has been published for this window yet."
        if population.included_records == 0
        else "Results below reflect the currently validated and included evidence."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Project Parallax — NEET Protest 2026 Media Analysis</title>
<style>
:root{{--ink:#18222f;--muted:#5c6878;--paper:#f6f4ef;--card:#fff;--line:#d9dde3;--blue:#315b7d;--gold:#c89b3c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
header{{background:#172b3a;color:white;padding:3rem max(5vw,1rem)}} header p{{max-width:70rem;color:#dbe6ed}}
main{{max-width:1180px;margin:auto;padding:2rem 1rem 4rem}} h1{{font-size:clamp(2rem,5vw,4rem);line-height:1.05;margin:.2rem 0}}
h2{{margin-top:0}} .eyebrow{{color:#f0c96b;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
.notice{{border-left:5px solid var(--gold);background:#fff8df;padding:1rem 1.25rem;margin:1.5rem 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1rem;margin:1.5rem 0}}
.card,section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1.25rem;box-shadow:0 2px 8px #18222f0d}}
.card strong{{display:block;font-size:1.8rem;color:var(--blue)}} section{{margin:1rem 0;overflow:auto}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:.65rem;text-align:left;border-bottom:1px solid var(--line)}}
.bar-cell{{width:45%}} .bar-cell span{{display:block;height:.75rem;background:var(--blue);border-radius:1rem;min-width:0}}
.empty,.muted{{color:var(--muted)}} footer{{padding:2rem max(5vw,1rem);background:#e8e5de;color:var(--muted)}}
code{{overflow-wrap:anywhere}} @media print{{body{{background:white}} section,.card{{box-shadow:none}}}}
.filters{{display:flex;flex-wrap:wrap;gap:.75rem;margin:1rem 0}} label{{font-weight:650}} input,select{{display:block;padding:.55rem;border:1px solid #9da7b3;border-radius:5px;min-width:10rem}}
.evidence-table{{min-width:1050px}} small{{color:var(--muted)}} q{{quotes:none}} [hidden]{{display:none!important}}
</style></head><body>
<header><div class="eyebrow">Project Parallax</div><h1>NEET Protest 2026<br>Media Analysis</h1>
<p>Rolling report window: <strong>{escape(window)}</strong>. This report measures observable coverage patterns and does not determine motives, honesty, ideology, or character.</p></header>
<main><div class="notice"><strong>Evidence status:</strong> {escape(status)} Machine-only and rejected records are excluded by default.</div>
<div class="grid"><div class="card"><span>Evidence records</span><strong>{population.included_records}</strong></div>
<div class="card"><span>Distinct source segments</span><strong>{population.included_distinct_segments}</strong></div>
<div class="card"><span>Human-review coverage</span><strong>{escape(review_percent)}</strong></div>
<div class="card"><span>Spoken material</span><strong>{population.included_spoken_duration_seconds:g}s</strong></div></div>
<section><h2>Targeted stance</h2><p class="muted">Counts are target-specific evidence records, not verdicts about truth or intent.</p>
<table><thead><tr><th>Target actor type</th><th>Stance</th><th>Records</th></tr></thead><tbody>{_stance_rows(summary)}</tbody></table></section>
{_bar_table('Topic attention — distinct spoken segments', summary.topic_duration_seconds, 'seconds')}
{_bar_table('Speaker representation — distinct spoken segments', summary.speaker_role_duration_seconds, 'seconds')}
{_bar_table('Evidence quality — distinct segments', summary.evidence_tier_segment_counts, 'segments')}
{_bar_table('Claim type and certainty', {f'{claim} / {certainty}': count for claim, values in summary.claim_by_certainty.items() for certainty, count in values.items()}, 'segments')}
{_bar_table('Packaging support', summary.packaging_support_counts, 'segments')}
{_bar_table('Review states', summary.review_state_counts, 'records')}
{_bar_table('Annotation conflicts', summary.segment_annotation_conflict_counts, 'segments')}
<section id="evidence"><h2>Timestamped evidence explorer</h2><p class="muted">A guest remains attributed to the guest; target actors and editorial speakers are displayed separately. Excerpts are limited public evidence, not complete transcripts.</p>
<div class="filters"><label>Search<input id="evidence-search" type="search" placeholder="Outlet, speaker, target, excerpt"></label>
<label>Stance<select id="stance-filter"><option value="">All</option>{''.join(f'<option value="{escape(value, quote=True)}">{escape(value.replace("_", " "))}</option>' for value in ('favourable','critical','neutral_descriptive','mixed','unclear','insufficient_evidence'))}</select></label>
<label>Tier<select id="tier-filter"><option value="">All</option>{''.join(f'<option value="{tier}">{tier}</option>' for tier in ('A','B','C','D'))}</select></label>
<label>Review<select id="review-filter"><option value="">All</option>{''.join(f'<option value="{value}">{escape(value.replace("_", " "))}</option>' for value in ('machine_only','human_reviewed','second_reviewed','rejected'))}</select></label></div>
<p id="filter-status" role="status">Showing {len(visible_records)} evidence record(s).</p>
<table class="evidence-table"><thead><tr><th>Source</th><th>Timestamp</th><th>Speaker</th><th>Target actor</th><th>Stance</th><th>Limited excerpt</th><th>Evidence / review</th></tr></thead><tbody>{_evidence_explorer(visible_records)}</tbody></table></section>
<section id="corrections"><h2>Correction history</h2><table><thead><tr><th>Correction</th><th>Record</th><th>Field</th><th>Corrected at</th><th>Reason</th><th>Metrics affected</th></tr></thead><tbody>{_correction_rows(corrections)}</tbody></table></section>
<section><h2>Reproducibility</h2><p>Dataset <strong>{escape(provenance.dataset_version)}</strong>; methodology {escape(provenance.methodology_version)}; taxonomy {escape(provenance.taxonomy_version)}; evidence schema {escape(provenance.schema_version)}.</p>
<p>Evidence SHA-256: <code>{escape(provenance.evidence_sha256)}</code>. Validated corrections: {provenance.correction_count}.</p></section>
</main><footer>Project Parallax · Politically neutral, evidence-first analysis · Topic durations may be non-exclusive.</footer>
<script>(()=>{{const rows=[...document.querySelectorAll('.evidence-row')],q=document.querySelector('#evidence-search'),stance=document.querySelector('#stance-filter'),tier=document.querySelector('#tier-filter'),review=document.querySelector('#review-filter'),status=document.querySelector('#filter-status');function apply(){{let shown=0;for(const row of rows){{const visible=(!q.value||row.dataset.search.includes(q.value.toLocaleLowerCase()))&&(!stance.value||row.dataset.stance===stance.value)&&(!tier.value||row.dataset.tier===tier.value)&&(!review.value||row.dataset.review===review.value);row.hidden=!visible;if(visible)shown++}}status.textContent=`Showing ${{shown}} evidence record(s).`}}for(const control of [q,stance,tier,review])control.addEventListener('input',apply)}})();</script>
</body></html>"""
