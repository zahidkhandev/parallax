# Methodology

## 1. Research posture and unit

Project Parallax measures observable presentation; it does not infer motives, honesty, ideology, character, or a correct “side.” The source unit is one timestamped spoken or packaging segment narrow enough to preserve the speaker, attributed source, topic, claim, certainty, and context. Because each stance annotation has exactly one target, one source segment may produce multiple evidence records when it addresses multiple actors. Never generalise a segment into an outlet-wide conclusion without a documented sampling design.

## 2. Collection and sampling

Record source URL, outlet, programme, title, publication/access times, and exact start/end seconds. Apply the event eligibility rule in [SCOPE.md](SCOPE.md), document the collection window and search strategy, deduplicate URLs, and retain exclusions. Report missing, deleted, inaccessible, and mixed-stream items so availability does not silently shape conclusions.

The active rolling window starts 1 July 2026. A report-through date is inclusive and fixed in each artifact; it defaults to the run date but can be supplied explicitly for reproducibility. An open manifest end means collection continues after that date—it does not allow future-dated material into an earlier report.

## 3. Attribution and representation

Record publisher, programme, evidence kind, speaker identity/role/affiliation, attributed sources, target actor, and editorial packaging separately. A guest statement is **never** an anchor or outlet statement. A quotation is attributed to its quoted source; the presenter’s act of selecting or challenging it may be a separate segment. Unknown identity stays unknown.

Representation metrics may include speaking time, turn count, quotation count, source diversity, and share of reviewed content. Publish the unit and denominator; presence alone does not establish endorsement.

## 4. Targeted stance

Every stance classification identifies one target actor by name and category. Create separate records when one statement takes different directions toward different actors.

- `favourable`: explicitly supports, praises, validates, or advocates for the target;
- `critical`: explicitly challenges, blames, condemns, or negatively evaluates the target;
- `neutral_descriptive`: describes the target without a discernible evaluation;
- `mixed`: contains material favourable and critical treatment that cannot responsibly be separated;
- `unclear`: direction is ambiguous after sufficient review; and
- `insufficient_evidence`: the available material cannot support a classification.

These labels describe a segment’s framing direction, not whether its claim is true.

## 5. Topics, frames, and loaded language

Use only topic and frame labels in the versioned `methodology/taxonomy.json` contract. Multiple labels are allowed but duplicates within one record are invalid. Loaded language is a word or phrase whose evaluative force exceeds a minimally descriptive alternative in context. Store the exact short term and a rationale; do not classify a term merely because it is emotionally salient. Compare rates only across equivalent languages, formats, and denominators, or disclose limitations.

## 6. Claims, certainty, and allegations

Classify claim type independently from stance: observed fact, verified fact, reported allegation, speaker allegation, opinion, question, speculation, prediction, quotation, or unclear. Certainty records whether it is explicitly or implicitly qualified, asserted as fact, contested, or unclear. Every allegation record must state whether qualification is present. This is presentation analysis, not fact-checking unless a separate verification protocol and sources are published.

## 7. Packaging-to-body support

Code headlines, thumbnails, descriptions, tickers, and other packaging as separate Tier C records. Compare their material proposition with the reviewed spoken portion using `supported_by_body`, `partially_supported`, `unsupported_in_reviewed_portion`, `contradicted_by_body`, `insufficient_transcript`, or `not_reviewed`. “Unsupported in the reviewed portion” does not mean false. Spoken-only records use `not_applicable`.

## 8. Evidence tiers

- **A — timestamped spoken evidence with verified source and speaker.**
- **B — exact reliable quotation or attribution without complete audiovisual verification.**
- **C — headline, thumbnail, description, or packaging evidence only.**
- **D — mixed stream, unresolved identity, or insufficient attribution.**

Tier describes provenance and attribution quality, not truth or political value.

## 9. Human review and evidence quality

Review states are `machine_only`, `human_reviewed`, `second_reviewed`, and `rejected`. Human review checks source, timestamp, speaker, attribution, target, excerpt, translation, topic, stance, claim, certainty, qualification, context, and tier. Second review requires a distinct reviewer. Rejected records remain excluded from published aggregates. Report record-weighted review coverage and tier distribution beside every aggregate; do not imply machine confidence is human verification.

## 10. Metrics and reporting

Permitted, separately reported measures include target-specific stance distributions; speaker/source representation; topic attention; loaded-language rates; claim/certainty and allegation-qualification distributions; packaging support; evidence-tier distributions; and human-review coverage. Publish counts, denominators, missingness, sampling period, methodology version, and uncertainty. Do **not** create one opaque universal bias score.

The reference aggregation pipeline excludes `machine_only` and `rejected` records from published analytical counts by default. Target-specific stance and review-state metrics use evidence records. Coverage metrics identify a distinct source segment by source URL, evidence kind, and exact start/end timestamps; they count its speaker, sources, topics, language, claim treatment, tier, packaging support, and duration once even when several target records refer to it. Conflicting annotations within a segment group are surfaced in diagnostics rather than silently selecting one.

Topic and speaker attention in seconds uses distinct spoken segments only. Because one segment may have multiple topic labels, topic durations are non-exclusive and must not be summed as though they partition total airtime. Outputs report both included evidence-record and distinct-segment counts, plus the number of additional target records. Empty datasets produce zero counts and `null` rather than a misleading percentage for human-review coverage.

## 11. Privacy, reproducibility, and corrections

Public records contain only URLs, metadata, timestamps, limited excerpts, annotations, derived metrics, transcript hashes, and review status. Complete working transcripts and media stay in the gitignored private workspace. A hash can establish which local transcript informed review without republishing it. Corrections preserve the prior value, reason, reviewer, date, and affected outputs under [CORRECTIONS.md](CORRECTIONS.md).

Generated metric artifacts preserve the evidence JSONL SHA-256 together with dataset, methodology, taxonomy, and schema versions and the validated correction count. This provenance identifies the precise public input without copying restricted working material into an output. Every artifact is validated against the Pydantic `AnalysisSummary` contract before writing; `schemas/analysis-summary.schema.json` provides the matching public Draft 2020-12 schema and is checked for drift in CI.
