# Public data

This directory is the publication boundary. `evidence-segments.jsonl` contains one timestamped evidence object per line and is validated against both the Pydantic model and matching JSON Schema. The initial file is intentionally empty: test fixtures are synthetic and no unreviewed observation is presented as real evidence.

Allowed public fields are URLs, source metadata, timestamps, limited necessary excerpts, original project annotations/translations, derived metrics, transcript hashes, and review status. Never add downloaded audio/video, subtitles, cookies, secrets, complete working transcripts, confidential information, or unnecessary personal data.

- `collection-manifest.json`: scope, methodology/data versions, collection window, and status.
- `evidence-segments.jsonl`: validated evidence records.
- `corrections.csv`: append-only public correction history.
- `reliability-annotations.jsonl`: independent reviewer labels for reliability rounds; no excerpts or transcripts.
- `source-inventory.jsonl`: discovered canonical URLs, inclusion/exclusion decisions, availability, and discovery metadata.

Third-party excerpts and metadata remain excluded from the project licences; see `DATA_LICENSE.md`.

Validate this directory with `python -m src validate`. Build a review-filtered metrics artifact with `python -m src analyze --output build/metrics.json`. The command validates the full dataset and manifest before computing anything, validates the result against the versioned analytical contract, and never emits a composite bias score.
