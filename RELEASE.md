# Release acceptance

A passing software test suite is necessary but not sufficient for a substantive Project Parallax data release. Maintainers must separate structural readiness from research validity and complete both checklists.

## Machine-enforced structural checks

Run:

```bash
python -m src readiness \
  --as-of YYYY-MM-DD \
  --output build/release-readiness.json \
  --require-ready
```

Strict mode exits with status 2 unless all of these are true:

- the public evidence dataset is nonempty;
- the collection window is closed for the release;
- the manifest status is `published`;
- `generated_at` is present;
- no evidence record is `machine_only`;
- no source-segment annotation conflicts remain; and
- analysis provenance matches the evidence checksum, dataset version, and report-through date.

The ordinary CI command omits `--require-ready`. It records readiness while allowing an honestly labelled collection-stage repository to continue development.

## Maintainer research checklist

Before changing the manifest to `published`, maintainers must confirm and record in release notes:

- [ ] The sampling window, search/discovery procedure, platforms, outlets, languages, and exclusions are documented.
- [ ] Inventory coverage and unavailable/deleted sources are reported.
- [ ] The reviewer handbook and current methodology version were used.
- [ ] A stratified reliability sample and per-label agreement are published with sample sizes.
- [ ] Machine transcription and translation limitations are reported by language where applicable.
- [ ] Every consequential named finding received the required independent second review.
- [ ] Target actors, speakers, quoted sources, anchors, guests, and outlets remain separately attributed.
- [ ] Counts identify record or deduplicated-segment denominators and multi-topic duration overlap.
- [ ] Uncertainty and small-sample suppression rules appropriate to the sampling design were applied.
- [ ] Corrections are validated and all metrics affected by corrections were rebuilt.
- [ ] The evidence JSONL, metrics JSON, HTML report, schemas, taxonomy, manifest, checksums, and release notes share one version.
- [ ] Third-party media and complete transcripts are absent from the release.
- [ ] A maintainer reviewed the prominent neutrality and limitations language.

## Release and rollback

Tag the exact commit used to build artifacts. Archive the public manifest, readiness JSON, metrics JSON, evidence checksum, and release notes together. If a material error is found, document it in the correction log, rebuild affected artifacts, publish a patch release, and retain the prior tagged release rather than rewriting its history.
