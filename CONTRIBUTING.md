# Contributing

Contributions that improve reproducibility, coverage balance, evidence quality, translations, accessibility, code, or methodology are welcome. Contributors must remain politically neutral: apply the same inclusion and annotation rules regardless of the actor or direction of a proposed finding.

## Evidence submissions

Use the timestamped-evidence issue form. Provide the original or most authoritative URL, outlet/programme metadata, publication time if known, exact start/end timestamps, a limited excerpt, original language and project-created translation if needed, speaker and attributed source, target actor, proposed stance, topic, claim type, certainty, allegation qualification, packaging support, tier, context, and uncertainty.

Do not submit downloaded media, subtitle files, complete transcripts, cookies, credentials, confidential material, unnecessary personal data, or unverifiable identity claims. A guest statement must remain attributed to the guest—not the anchor, programme, or outlet. Every stance requires a target actor.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest
python -m src.validate_public_data
```

When changing `EvidenceSegment`, regenerate the checked-in evidence schema with Pydantic, review the semantic diff, and add tests. When changing a controlled enum, regenerate both the evidence schema and `methodology/taxonomy.json`. When changing analytical fields or invariants, regenerate `schemas/analysis-summary.schema.json`. JSONL contains exactly one complete object per nonblank line, with globally unique `record_id` values and no duplicate topic or frame labels.

When correcting a published record, update the JSONL and append—not replace—a valid row in `public-data/corrections.csv`. Use a unique `cor-` identifier, a timezone-aware correction timestamp, a dotted field path, differing old/new values, a reason, reviewer ID, and an exact lowercase `true` or `false` metrics-impact value. Run the full validator before opening a pull request.

## Review and publication

Reviewers verify event eligibility, source, timestamp, speaker, attribution, target, excerpt, translation, context, labels, and rights boundary. Named or high-severity claims require second review by a distinct reviewer. Machine-only records may support triage but must not be presented as confirmed allegations. Conflicts of interest should be disclosed and reviewers should recuse where impartial review is not possible.

Be descriptive and proportionate. Do not allege motive, dishonesty, ideology, coordination, or character from a framing annotation. Corrections and appeals follow [CORRECTIONS.md](CORRECTIONS.md).

## Contribution licensing

Code contributions are accepted under Apache-2.0. By contributing original annotations, documentation, translations, or derived data, you agree to CC BY 4.0. You must have the right to contribute the material. Third-party media and transcripts are excluded from both project licences.
