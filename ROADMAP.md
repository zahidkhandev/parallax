# Roadmap

This roadmap separates implemented repository infrastructure from research work that requires a declared collection window and real reviewed evidence. Checked items are available in the repository; unchecked items remain before a substantive public release.

## Foundation — substantially implemented

- [x] Versioned evidence model and generated JSON Schema.
- [x] Controlled taxonomy with drift detection.
- [x] Manifest, correction-log, public/private-boundary, and provenance validation.
- [x] Review-filtered, segment-deduplicated descriptive analytics.
- [x] Versioned analytical-output model and generated JSON Schema.
- [x] CLI, tests, and CI for all generated contracts and the empty public scaffold.
- [x] Publish a reviewer handbook with attribution and multilingual edge cases.
- [ ] Add release signing or attestations after a hosting/release policy is chosen.

## Phase 1 — Protocol and inventory

- [x] Define a versioned source-inventory contract, discovery protocol, and coverage-audit tool.
- [x] Declare the first pilot window, discovery surfaces, frozen queries, result limits, and exclusion handling.
- [x] Implement scheduled/manual frozen-query discovery with execution provenance and review PRs.
- [ ] Complete the first successful live search run and review its execution log.
- [ ] Build and deduplicate the source inventory without selecting on expected stance.
- [ ] Verify outlet, programme, title, publication date, availability, and mixed-stream metadata.
- [ ] Audit inventory coverage by outlet, language, format, and actor before annotation.

## Phase 2 — Private processing and public evidence

- [ ] Process lawfully accessed captions or local transcription only in `private-workspace/`.
- [ ] Measure language-specific transcription and timestamp error on a documented sample.
- [ ] Segment speaker turns and distinguish guests, anchors, correspondents, quotations, and packaging.
- [ ] Publish only limited excerpts, timestamps, annotations, transcript hashes, and review status.

## Phase 3 — Reliability and review

- [ ] Train reviewers with neutral examples and adjudication rules.
- [x] Implement validated independent double-coding records and per-label agreement tooling.
- [ ] Double-code a stratified real-data pilot and publish per-label agreement with sample sizes.
- [ ] Revise ambiguous labels based on pilot disagreements and version the methodology.
- [ ] Second-review named or high-severity findings.
- [ ] Audit actor, outlet, language, format, evidence-tier, and review coverage.

## Phase 4 — Analysis and dashboard

- [x] Implement target-specific stance and deduplicated coverage metrics without a composite score.
- [x] Expose counts, denominators, review coverage, evidence quality, conflicts, and provenance.
- [ ] Add uncertainty intervals and suppression rules suitable for the final sampling design.
- [x] Build a dependency-free accessible rolling summary report with an honest empty state.
- [x] Add the interactive timestamped evidence explorer, source links, record filters, and correction history.
- [x] Link chart categories to filtered evidence; expose methodology versions and correction history.
- [x] Add a deterministic structural accessibility gate for generated reports.

## Phase 5 — Reproducible releases

- [x] Validate data, generated contracts, and analytics in CI.
- [x] Embed dataset versions and evidence checksums in analytical artifacts.
- [x] Define machine-enforced release acceptance criteria and a maintainer research checklist.
- [x] Build deterministic public-only draft and strict release bundles with checksums.
- [ ] Publish the first versioned reviewed dataset, metrics artifact, and release notes together.
- [ ] Exercise correction, rebuild, rollback, and archival procedures on a release candidate.
