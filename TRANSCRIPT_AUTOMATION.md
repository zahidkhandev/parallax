# Transcript and spoken-evidence automation

Project Parallax can analyse timed captions and locally transcribed media without
publishing complete transcripts or downloaded media.

## What the pipeline does

`python -m src.transcript_evidence`:

1. selects sources already marked `included` and `available`;
2. prefers a local timed transcript in the private workspace;
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

The first hosted pilot attempted 25 included audiovisual sources. No usable timed
caption was acquired: publisher pages exposed no directly usable caption tracks and
YouTube rejected requests from the GitHub-hosted datacenter IP. This is why the
self-hosted fallback below is required for the current collection.

## Self-hosted acquisition and ASR

The `Transcribe media on self-hosted runner` workflow is manually dispatched and runs
only on a runner carrying the label `parallax-transcriber`. Register a Linux or macOS
self-hosted GitHub Actions runner, add that custom label, and keep its working directory
private.

The workflow:

1. tries subtitle and automatic-caption acquisition with yt-dlp;
2. optionally downloads bounded audio when captions are unavailable;
3. keeps all third-party media and complete captions outside the repository checkout;
4. runs Faster-Whisper locally;
5. generates Tier D, `machine_only` spoken evidence;
6. validates all public records; and
7. opens a separate evidence pull request only when public evidence changed.

Audio downloading is disabled by default and must be explicitly selected when manually
dispatching the workflow. Use it only where acquisition and private research use are
lawful. Browser cookies are optional and stay on the self-hosted machine.

## Equivalent local commands

```bash
python -m pip install -e '.[dev,transcripts,asr,media]'
python -m src.media_acquisition \
  --as-of 2026-07-29 \
  --download-audio \
  --cookies-from-browser chrome \
  --report build/media-acquisition-report.json
python -m src.transcript_evidence \
  --as-of 2026-07-29 \
  --network \
  --local-asr \
  --private-root private-workspace/transcripts \
  --whisper-model small \
  --whisper-device cpu \
  --whisper-compute-type int8 \
  --report build/transcript-evidence-report.json
```

Omit `--cookies-from-browser` when it is unnecessary. For an NVIDIA GPU, use a
compatible local CUDA setup and typically select
`--whisper-device cuda --whisper-compute-type float16`.

## Local caption and media formats

The transcript pipeline accepts:

```text
private-workspace/transcripts/<source_id>.jsonl
private-workspace/transcripts/<source_id>.json
private-workspace/transcripts/<source_id>.vtt
private-workspace/transcripts/<source_id>.srt
private-workspace/media/<source_id>.<wav|mp3|m4a|mp4|webm|mkv|mov|ogg|flac>
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
- the generation and acquisition reports accompany exploratory metrics; and
- no machine-only record should be presented as a confirmed allegation or outlet verdict.
