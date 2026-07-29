# Transcript acquisition pilot 001

## Window and population

- report-through date: 29 July 2026
- eligible population: included, available audiovisual-style inventory sources
- candidate sources attempted by the hosted caption workflow: 25

## Hosted result

The GitHub-hosted caption-first pilot acquired 0 timed transcripts and generated 0
spoken-evidence records. All 25 attempts were retained in
`build/transcript-evidence-report.json` with a source identifier, URL and failure
reason.

The two observed failure classes were:

1. publisher pages did not expose a directly usable timed `<track>` caption; and
2. embedded YouTube transcript requests were blocked from the GitHub-hosted datacenter
   IP.

This result is an acquisition limitation, not evidence that the underlying videos lack
captions or speech.

## Follow-up design

The repository therefore provides a manually dispatched self-hosted workflow. It tries
caption acquisition from a user-controlled network, can optionally acquire bounded
audio where lawful, runs Faster-Whisper locally, keeps complete transcripts and media
outside Git, and opens a separate pull request containing only short timestamped
excerpts, hashes, annotations and audit reports.

Every automatically generated spoken record remains Tier D and `machine_only`; default
analytics exclude it until review.
