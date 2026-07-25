# Corrections and appeals

Project Parallax treats corrections as part of the evidence record, not as silent cleanup. Anyone may report an incorrect source, timestamp, attribution, target, excerpt, translation, label, review state, or aggregate.

## Process

1. Identify the record ID, field, current value, proposed value, source, and reason.
2. A reviewer checks the original evidence under the current methodology; a second reviewer handles disputed or high-severity changes.
3. Accepted changes update the JSONL record and append a row to `public-data/corrections.csv` with old/new values, UTC date, reason, reviewer identifier, and affected metrics.
4. Derived outputs are rebuilt. Release notes disclose material aggregate changes.
5. Rejected requests receive a documented evidence-based explanation and may be appealed with new evidence.

## Machine-readable log

`public-data/corrections.csv` is append-only and uses this exact header:

```text
correction_id,record_id,corrected_at,field,original_value,corrected_value,reason,reviewer,metrics_affected
```

Correction IDs begin with `cor-` and are unique. `corrected_at` includes a timezone, `field` is a dotted evidence-model path, and `metrics_affected` is exactly `true` or `false`. The old and new values must differ, and the referenced evidence record must remain present so a correction is auditable. The production validator enforces these rules.

Personal information in a correction request should be minimised. Good-faith correction requests are evaluated by the same standard regardless of the person, outlet, or political direction involved.
