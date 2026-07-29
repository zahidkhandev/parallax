# Collection protocol

## Objective

Build a reproducible inventory of news-media items connected to the NEET 2026 protests from 1 July 2026 through each report-through date. Discovery and inclusion must not depend on an expected stance, actor treatment, or anticipated finding.

## Before collection

For each collection round, document in release notes or a versioned protocol supplement:

- report-through date and time zones used for publication dates;
- platforms and news surfaces searched;
- outlet list and how it was constructed;
- query strings in each language and script;
- search dates, result-depth limits, and pagination limits;
- handling of recommendations, syndicated copies, deleted items, and inaccessible results; and
- any planned stratification or caps by outlet, format, language, or day.

Do not silently tune queries after seeing whether results appear favourable or critical toward an actor. Record material query revisions and rerun comparable searches where feasible.

## Inventory records

Store one line per discovered canonical URL in `public-data/source-inventory.jsonl`. Record source ID, URL, outlet, programme, title, publication/access timestamps, original language, format, availability, eligibility, discovery method/query, and notes. Mixed streams may include the eligible start/end range. Do not add downloaded media, subtitles, complete transcripts, cookies, or credentials.

Statuses:

- `included`: verified coverage within event scope and the reporting window;
- `excluded`: reviewed and outside the published eligibility rule, with a reason; and
- `pending_review`: not yet resolved and unavailable for evidence records.

Availability is separate from eligibility. Preserve records for deleted, unavailable, geo-restricted, or unknown sources so missingness remains visible.

## Deduplication

Use the original or most authoritative available publisher URL as canonical. The validator rejects duplicate source IDs and canonical URLs. Syndicated or materially distinct versions may remain separate only when their URLs and editorial packaging are distinct; document the relationship in notes.

## Eligibility review

Apply [SCOPE.md](SCOPE.md) before examining or coding stance. Keyword matches alone are insufficient. For mixed streams, verify a separable eligible segment. Every public evidence record must reference a URL marked `included`; excluded or pending sources cannot enter analysis.

## Coverage audit

Run:

```bash
python -m src inventory-schema
python -m src inventory-audit --output build/inventory-audit.json
```

Publish source totals and separate breakdowns by eligibility, availability, format, language, and included outlet. These counts describe collection coverage; they do not rank outlet quality or political bias. Inspect imbalances before annotation and document any corrective collection round.

## Freeze and update

For a versioned release, close the collection window, freeze the inventory, archive the queries and audit, and record unavailable sources. Later discoveries belong in a new dataset version rather than a silent rewrite. Corrections to inventory metadata must be documented in release notes until a dedicated inventory correction log is adopted.
