# Project Parallax — NEET Protest 2026 Media Analysis

[![Validate](https://github.com/project-parallax/neet-protest-2026-media-analysis/actions/workflows/validate.yml/badge.svg)](https://github.com/project-parallax/neet-protest-2026-media-analysis/actions/workflows/validate.yml)

**Project Parallax** is a politically neutral, open-source research repository for measuring observable patterns in media coverage connected specifically to the **NEET 2026 protests**. It does not begin with a conclusion that any participant, institution, party, journalist, programme, or outlet is correct or biased.

> **Prominent disclaimer:** This project analyses observable coverage patterns in identified media items. It does **not** determine motives, honesty, ideology, or character. Its annotations are bounded, reviewable observations—not verdicts about people or organisations.

## What the project measures

Each observation is a timestamped spoken or editorial-packaging segment. Records measure:

- favourable, critical, neutral, mixed, unclear, or insufficient-evidence stance **toward an explicitly named target actor**;
- representation of speakers and attributed sources, without treating a guest's words as an anchor's or outlet's words;
- topic attention and frame labels;
- loaded-language terms with a written rationale;
- claim type, certainty, and whether allegations are qualified;
- whether headline, thumbnail, description, or ticker claims are supported by reviewed spoken content; and
- evidence tier, transcript hash, review state, and human-review coverage.

Target actors include protest organisers; students and candidates; parents; government representatives; education and examination authorities; police; ruling and opposition parties; courts and public institutions; anchors and correspondents; guests and experts; and other actors directly relevant to the event. The same rules apply regardless of political direction.

Project Parallax never collapses these dimensions into one opaque universal bias score. Aggregate results must remain traceable to records, denominators, evidence quality, and review coverage.

## Evidence and review labels

| Tier | Definition |
|---|---|
| **A** | Timestamped spoken evidence with verified source and speaker |
| **B** | Exact reliable quotation or attribution without complete audiovisual verification |
| **C** | Headline, thumbnail, description, or packaging evidence only |
| **D** | Mixed stream, unresolved identity, or insufficient attribution |

Review states are `machine_only`, `human_reviewed`, `second_reviewed`, and `rejected`. Machine-only output is triage material, not a confirmed public finding.

## Public/private boundary

`public-data/` is limited to URLs, source metadata, timestamps, short necessary excerpts, project annotations and translations, derived metrics, transcript hashes, and review status. Downloaded media, subtitles, cookies, secrets, and complete working transcripts are prohibited from public data. Keep complete working transcripts and lawful local media only in the gitignored `private-workspace/` directory.

## Quick start

Python 3.11 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest
python -m src schema
python -m src analysis-schema
python -m src reliability-schema
python -m src inventory-schema
python -m src taxonomy
python -m src validate
python -m src analyze --output build/metrics.json
python -m src report --output dashboard/index.html --metrics-output dashboard/metrics.json
python -m src accessibility --report dashboard/index.html --output build/accessibility.json --require-pass
python -m src readiness --output build/release-readiness.json
python -m src reliability --output build/reliability.json
python -m src inventory-audit --output build/inventory-audit.json
python -m src discover --report-through 2026-07-29 --max-results 100
python -m src bundle --draft --output build/parallax-bundle
```

The validator applies both the Pydantic contract in `src/models.py` and the matching Draft 2020-12 JSON Schema in `schemas/evidence-segment.schema.json` to every JSONL line. It also verifies the generated controlled taxonomy, rejects duplicate IDs and labels, validates the correction log and its record references, checks that the collection manifest's record count is exact, and fails when a checked-in contract drifts from the model.

The analysis command validates before reading, validates its result against the Pydantic analytical contract, and writes JSON atomically. The matching generated contract is `schemas/analysis-summary.schema.json`. Every artifact identifies the dataset, methodology, taxonomy, and schema versions; the exact evidence-file SHA-256; and the number of recorded corrections. By default it excludes `machine_only` and `rejected` records from analytical counts, while still reporting their effect on review coverage. Target-specific stance remains record-based, while coverage, speaker, source, topic, claim, tier, packaging, and duration metrics deduplicate the underlying source URL/kind/timestamp segment so multiple target annotations do not inflate attention. Conflicts inside a segment group are reported explicitly. Spoken-topic and speaker attention are reported in seconds; multi-topic durations are non-exclusive. Use `--include-machine-only` only for clearly labelled exploratory work; use `--include-rejected` only for quality-control analysis.

The rolling reporting window begins **1 July 2026**. `--as-of YYYY-MM-DD` fixes the inclusive report-through date for a reproducible run; when omitted it uses the current date. The collection remains open-ended so the same commands continue to include eligible coverage after today. Every nonempty-window record must have a publication timestamp inside the declared window. `report` produces a dependency-free, accessible HTML file plus optional matching metrics JSON, chart-to-evidence filter links, a timestamped evidence explorer with client-side filters, and validated correction history. `accessibility --require-pass` enforces deterministic report-level checks for language, landmarks, titles, headings, control labels, unique IDs, table headers, image alternatives, and external resources.

`readiness` records deterministic structural release checks. Add `--require-ready` in a release job to fail unless the dataset is nonempty, its window is closed, the manifest is published and timestamped, machine-only evidence and annotation conflicts are absent, and analytical provenance matches. Structural readiness does not replace the human research checklist in [RELEASE.md](RELEASE.md).

Independent double-coding labels in `public-data/reliability-annotations.jsonl` are evaluated per field with `reliability`. The output reports pair counts, excluded groups, categorical percent agreement and Cohen’s kappa, and multi-label exact agreement and mean Jaccard. It deliberately does not collapse reliability into one score. Reviewers must follow [REVIEWER_HANDBOOK.md](REVIEWER_HANDBOOK.md).

All evidence URLs must first appear as `included` records in `public-data/source-inventory.jsonl`. The inventory retains pending and excluded discoveries, availability failures, discovery methods, queries, languages, and formats so collection coverage and missingness are auditable. `inventory-audit` reports these dimensions separately without treating them as outlet-quality or political scores. Follow [COLLECTION_PROTOCOL.md](COLLECTION_PROTOCOL.md).

The first pilot discovery design is frozen in `methodology/collection-round-001.json` for 1–29 July 2026. It declares English and Hindi query families, result-depth and deduplication rules, and collection limitations. Its planned status and execution log distinguish intended searches from searches that were actually run. Contributors can propose URLs through the source-discovery issue form; proposals remain pending until scope and metadata review.

`discover` executes every frozen English and Hindi query against a news-search RSS feed, records one execution entry per query, merges canonical result URLs without duplication, and adds every new result as `pending_review`. It never creates stance or evidence annotations. The separate `Discover source candidates` GitHub Actions workflow runs daily or on demand, validates the inventory, pushes a bot-owned branch, and opens a human-review pull request. Repository settings must permit GitHub Actions to create pull requests. Search feeds can return aggregator links or incomplete metadata, so reviewers must verify the original publisher URL, publication time, event scope, language, availability, and media format before changing eligibility to `included`.

`bundle` assembles the validated public data, generated metrics, HTML report, readiness and reliability reports, inventory audit, schemas, taxonomy, licences, and methodology documents into one checksummed directory. Strict mode refuses a bundle until release gates pass; `--draft` produces an explicitly labelled, reproducible collection-stage bundle for CI and review. Private workspace files and downloaded media are never copied.

When an intentional model change alters the public contract, regenerate the schema and commit both changes together:

```bash
python -m src schema --write
python -m src schema
python -m src analysis-schema --write
python -m src analysis-schema
python -m src taxonomy --write
python -m src taxonomy
```

## Repository map

```text
public-data/       Publishable JSONL evidence and dataset metadata
private-workspace/ Gitignored complete transcripts and local working media
schemas/           Machine-readable public data contract
methodology/       Generated, machine-checked controlled taxonomy
src/               Models, validation, CLI, and descriptive analytics
tests/             Model, validator, CLI, manifest, and analytics tests
dashboard/         Generated accessible report and matching metrics
.github/            CI and structured evidence intake
```

Read [SCOPE.md](SCOPE.md), [METHODOLOGY.md](METHODOLOGY.md), and [CONTRIBUTING.md](CONTRIBUTING.md) before submitting evidence. Published errors follow [CORRECTIONS.md](CORRECTIONS.md).

## Licensing and third-party rights

Code is licensed under [Apache-2.0](LICENSE). Original annotations, documentation, translations, and derived data are licensed under [CC BY 4.0](DATA_LICENSE.md). **Neither licence grants rights in third-party media, transcripts, subtitles, images, logos, or quotations; those materials remain excluded.** See [NOTICE.md](NOTICE.md).
