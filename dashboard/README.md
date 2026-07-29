# Static report

`index.html` is the current dependency-free, accessible Project Parallax report and `metrics.json` is its matching validated analytical artifact. The checked-in report covers **1 July 2026 through 29 July 2026** and correctly displays an empty-data state until reviewed evidence is published.

Regenerate through any inclusive date with:

```bash
python -m src report \
  --as-of 2026-07-29 \
  --output dashboard/index.html \
  --metrics-output dashboard/metrics.json
```

The report exposes targeted stance, topic and speaker attention, evidence quality, claim treatment, packaging support, review coverage, annotation conflicts, and reproducibility metadata. Chart categories deep-link to matching explorer filters. The timestamped evidence explorer keeps speaker and target attribution separate, links to sources, uses limited excerpts, and filters by text, stance, tier, review state, target type, and speaker role. Validated correction history appears alongside the evidence. The report states whether counts use target-specific evidence records or deduplicated source segments, retains the neutrality disclaimer, and contains no external scripts, fonts, trackers, or network dependencies.

The CI structural audit checks language, landmarks, titles, headings, labels, unique IDs, table headers, image alternatives, and external resources. Manual keyboard and screen-reader usability testing and uncertainty or suppression displays remain dependent on real users and a final sampling design.
