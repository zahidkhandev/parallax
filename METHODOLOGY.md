# Methodology

## 1. Unit of analysis

The primary analytical unit is a **timestamped speech or packaging segment**, not an entire channel.

A segment should be sufficiently narrow to preserve:

- Speaker
- Target
- Topic
- Claim type
- Evidentiary context
- Stance or frame
- Start and end timestamps

## 2. Attribution hierarchy

Record these independently:

1. Publisher or outlet
2. Programme
3. Content format
4. Speaker identity
5. Speaker role
6. Quoted or attributed source
7. Target entity
8. Editorial packaging source

A guest's statement is not automatically an anchor's statement. An anchor's statement is not automatically a formal institutional position of the outlet.

## 3. Stance direction

Allowed values:

- `favourable`
- `critical`
- `neutral_descriptive`
- `mixed`
- `unclear`
- `insufficient_evidence`

Stance is always recorded **toward a named target**.

## 4. Framing categories

Initial categories:

- `legitimising`
- `delegitimising`
- `criminalising`
- `victimising`
- `heroising`
- `law_and_order`
- `civil_rights`
- `institutional_accountability`
- `institutional_trust`
- `public_disruption`
- `electoral_political`
- `conspiratorial`
- `procedural_legal`
- `human_interest`
- `evidence_verification`
- `other`

More than one category may apply. Each category must be supported by a written rationale and evidence excerpt.

## 5. Claim type

- `observed_fact`
- `verified_fact`
- `reported_allegation`
- `speaker_allegation`
- `opinion`
- `question`
- `speculation`
- `prediction`
- `quotation`
- `unclear`

## 6. Certainty treatment

- `explicitly_qualified`
- `implicitly_qualified`
- `asserted_as_fact`
- `contested`
- `unclear`

## 7. Evidence presentation

Record whether the segment provides:

- Direct audiovisual evidence
- Documents or records
- Named source attribution
- Unnamed source attribution
- Counter-position
- Correction or qualification
- No supporting evidence within the segment
- Evidence outside the sampled segment

This field does not independently determine whether a claim is true or false.

## 8. Packaging analysis

Analyse headlines, thumbnails, tickers and descriptions separately from spoken content.

Possible outcomes:

- `supported_by_body`
- `partially_supported`
- `unsupported_in_reviewed_portion`
- `contradicted_by_body`
- `insufficient_transcript`
- `not_reviewed`

Do not state that packaging is false merely because a matching phrase is absent.

## 9. Machine processing

Machine-generated transcripts and classifications must record:

- Model and version
- Processing date
- Detected language
- Confidence where available
- Transcript source
- Whether timestamps are word-level or segment-level
- Human-review status

Machine-only records may be used for triage and exploratory aggregate analysis, but not for high-severity public accusations.

## 10. Human review

A reviewer verifies:

- Source identity
- Speaker identity or role
- Timestamp
- Excerpt
- Translation
- Target
- Claim type
- Stance
- Frame
- Context sufficiency

Sensitive findings should receive a second independent review.

## 11. Metrics

Preferred public metrics include:

- Critical and favourable framing by target
- Topic attention share
- Speaker and source representation
- Loaded-language frequency
- Allegation-certainty distribution
- Counter-position inclusion
- Headline-body relationship
- Evidence-tier distribution
- Human-review coverage

Avoid a single unexplained universal bias score.

## 12. Corrections

Every correction should retain:

- Original value
- Corrected value
- Reason
- Date
- Reviewer
- Affected outputs
- Whether aggregate metrics changed

See [CORRECTIONS.md](CORRECTIONS.md).
