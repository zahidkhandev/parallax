# Reviewer handbook

## Purpose and posture

Reviewers describe observable media presentation connected only to the NEET 2026 protests. Do not decide which political or institutional side is correct and do not infer motive, honesty, ideology, or character. Apply identical evidence thresholds to every actor and record uncertainty rather than forcing a conclusion.

## Review sequence

1. Confirm event eligibility and the 1 July 2026–report-through publication window.
2. Open the original or most authoritative available source and verify title, outlet, programme, date, and timestamps.
3. Identify the actual speaker and any quoted or attributed source. Never convert a guest statement into an anchor or outlet statement.
4. Select a narrow segment with sufficient surrounding context.
5. Create one record per target actor. If direction differs by target, keep the same source segment but use separate target-specific stance records.
6. Classify topic, frame, claim type, certainty, allegation qualification, evidence tier, and packaging relationship independently.
7. Record loaded language only when the exact term and contextual rationale are supportable.
8. Mark uncertainty, preserve a limited excerpt, and submit for the required review state.

## Attribution edge cases

| Situation | Rule |
|---|---|
| Anchor introduces a guest, then the guest makes an allegation | Speaker is `guest`; the allegation is not the anchor’s or outlet’s statement. |
| Anchor quotes an official document | Speaker role may be `quoted_source` for the quotation; analyze the anchor’s framing as a separate segment when warranted. |
| Correspondent paraphrases an unnamed source | Speaker is `correspondent`; record unnamed attribution without inventing an identity. |
| Panelists speak over one another | Split only when turns remain attributable; otherwise use Tier D and `unknown` where necessary. |
| Headline makes a claim absent from reviewed speech | Create separate Tier C packaging evidence and use the bounded packaging-support label; absence is not proof of falsity. |
| Institutional statement is read verbatim | Attribute the statement to the institution and distinguish the presenter’s own language. |

## Stance decisions

Stance always has a named target. Use `neutral_descriptive` for description without discernible evaluation, `mixed` only when favourable and critical material cannot responsibly be separated, `unclear` when direction remains ambiguous after context review, and `insufficient_evidence` when the available material cannot support classification. Stance does not establish truth.

Questions are not automatically critical. Praise is not automatically favourable toward every actor mentioned. Reported criticism is attributed to its source; the act of reporting it is not automatically the outlet’s endorsement.

## Claims, certainty, and allegations

Separate claim type from stance. An allegation remains an allegation even when confidently delivered. Mark `allegation_qualified` according to the reviewed presentation: words equivalent to “alleged,” explicit attribution, or an immediate meaningful caveat may qualify it; tone alone does not. A question mark does not necessarily qualify a proposition if the spoken presentation asserts it as fact.

## Multilingual review

- Review in the original language whenever a qualified reviewer is available.
- Preserve the original limited excerpt and add a faithful project translation; do not translate tone into stronger certainty.
- Retain culturally specific terms when no precise equivalent exists and explain them in context notes.
- Code loaded language in the original language. Translated wording alone is not evidence that the source used a loaded term.
- Record code-switching with the most specific valid language tag for the excerpt and explain material switches.
- Machine translation or transcription must remain visibly machine-only until a qualified human checks wording and timestamps.

## Context sufficiency

Review enough material before and after the segment to resolve speaker, target, negation, quotation, sarcasm, and rebuttal. Extend timestamps when a short excerpt would reverse or conceal meaning. Use `insufficient_evidence` rather than reconstructing missing audio or assuming a clipped statement’s context.

## Independent double coding

For a reliability round, reviewers work independently and do not see the other reviewer’s labels before submission. Use pseudonymous reviewer IDs. The reliability JSONL stores labels only—no complete transcripts or private notes. Each round/record/reviewer combination is unique. After metrics are frozen, adjudicate disagreements separately and document rule changes in a new methodology version.

Run:

```bash
python -m src reliability --output build/reliability.json
```

Report pair count, exclusions, percent agreement and Cohen’s kappa for each categorical label, and exact agreement plus mean Jaccard for topic/frame sets. Do not combine these into one universal reliability score. Agreement measures consistency, not correctness.

## Escalation and rejection

Second review is required for consequential named findings. Reject a record when the source is outside scope, timestamps or attribution cannot be verified, the excerpt is excessive, private data is unnecessary, rights boundaries are violated, or requested corrections remain unresolved. Rejection is a workflow state, not a judgment about the actor or outlet.
