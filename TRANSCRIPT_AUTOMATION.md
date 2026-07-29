# Transcript and spoken-evidence automation

Project Parallax can analyse timed captions and locally transcribed media without
publishing complete transcripts or downloaded media.

## What the pipeline does

`python -m src.transcript_evidence`:

1. selects sources already marked `included` and `available`;
2. prefers a local timed transcript in `private-workspace/transcripts/`;
3. can retrieve public YouTube captions or publisher `<track>` captions with `--network`;
4. can run Faster-Whisper over lawfully obtained local media with `--local-asr`;
5. groups adjacent cues into bounded context windows;
6. extracts explicitly named target actors and produces one record per target;
7. commits only timestamps, short excerpts, annotations and a transcript SHA-256; and
8. marks every result `machine_only` and Tier D because speaker identity is unverified.

Complete transcripts are cached only under the gitignored private workspace.

## Hosted caption run

Install the small caption dependency and run:

```bash
python -m pip install -e '.[dev,transcripts]'
python -m src.transcript_evidence \
  --as-of 2026-07-29 \
  --network \
  --report build/transcript-evidence-report.json
python -m src validate --as-of 2026-07-29
python -m src analyze \
  --as-of 2026-07-29 \
  --include-machine-only \
  --output build/transcript-machine-metrics.json
```

The `Generate transcript evidence` workflow performs this caption-first run. Network
failures, disabled captions, inaccessible pages and sources without timed text are
reported rather than silently omitted.

## Local ASR fallback

Put lawfully obtained media in:

```text
private-workspace/media/<source_id>.<wav|mp3|m4a|mp4|webm|mkv|mov|ogg|flac>
```

Then run on a machine with sufficient CPU/GPU resources:

```bash
python -m pip install -e '.[dev,transcripts,asr]'
python -m src.transcript_evidence \
  --as-of 2026-07-29 \
  --network \
  --local-asr \
  --whisper-model small \
  --whisper-device cpu \
  --whisper-compute-type int8
```

For an NVIDIA GPU, use a compatible local CUDA setup and typically select
`--whisper-device cuda --whisper-compute-type float16`.

## Local caption formats

The pipeline accepts:

```text
private-workspace/transcripts/<source_id>.jsonl
private-workspace/transcripts/<source_id>.json
private-workspace/transcripts/<source_id>.vtt
private-workspace/transcripts/<source_id>.srt
```

A JSONL cue may contain:

```json
{"start": 12.4, "end": 18.9, "text": "Exact cue text", "speaker": "Optional label"}
```

`duration` may replace `end`.

## Interpretation boundary

Automated captions and ASR can omit words, hallucinate text, merge speakers and shift
timestamps. Lexical rules can also misidentify quotation, target, stance, topic and
frame. Therefore:

- generated spoken records remain `machine_only`;
- unverified speaker attribution uses Tier D;
- default analytics continue to exclude these records;
- the generation report must accompany exploratory machine-only metrics; and
- no machine-only record should be presented as a confirmed allegation or outlet verdict.
