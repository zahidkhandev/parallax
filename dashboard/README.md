# Static report

`index.html` is the current dependency-free, accessible Project Parallax report and `metrics.json` is its matching validated analytical artifact. The checked-in report covers **1 July 2026 through 25 July 2026** and correctly displays an empty-data state until reviewed evidence is published.

Regenerate through any inclusive date with:

```bash
python -m src report \
  --as-of 2026-07-25 \
  --output dashboard/index.html \
  --metrics-output dashboard/metrics.json
```

The report exposes targeted stance, topic and speaker attention, evidence quality, claim treatment, packaging support, review coverage, annotation conflicts, and reproducibility metadata. Its timestamped evidence explorer keeps speaker and target attribution separate, links to sources, uses limited excerpts, and filters by text, stance, tier, and review state. Validated correction history appears alongside the evidence. The report states whether counts use target-specific evidence records or deduplicated source segments, retains the neutrality disclaimer, and contains no external scripts, fonts, trackers, or network dependencies.

The remaining dashboard work is formal keyboard/screen-reader usability testing and uncertainty or suppression displays after a real sampling design exists.
