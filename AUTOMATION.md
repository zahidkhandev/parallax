# Automated evidence generation

`python -m src.automated_evidence` generates conservative Tier C headline-packaging records from sources already marked `included` and `available` in the source inventory.

The generator:

- processes accepted inventory metadata only;
- extracts explicitly signalled target actors with deterministic English and Hindi rules;
- assigns exploratory topic, frame, stance, claim, certainty, and loaded-language labels;
- writes every generated record as `machine_only`;
- preserves non-automated evidence records;
- updates the collection manifest record count;
- writes a machine-readable generation report; and
- remains idempotent by replacing its own previous machine-only headline records.

It does not fetch or analyse article bodies, thumbnails, transcripts, audio, or video. It does not verify factual claims. Machine-only records remain excluded from default published analytics.

Run the full current collection through 29 July 2026 with:

```bash
python -m src.automated_evidence --as-of 2026-07-29
python -m src validate --as-of 2026-07-29
python -m src analyze --as-of 2026-07-29 --include-machine-only --output build/machine-metrics.json
```

The `Generate machine evidence` workflow runs this sequence on the automation pull request and commits the generated evidence, manifest, report, and exploratory metrics back to the branch.
