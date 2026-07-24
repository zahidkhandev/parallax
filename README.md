# Project Parallax

## NEET Protest 2026 Media Analysis

**Project Parallax** is an open-source, evidence-first study of how Indian news media framed the NEET 2026 protests and the actors involved.

The project does **not** begin with a conclusion that any outlet, protest group, government body, political party, police force, journalist, or institution is correct or biased. It measures observable coverage patterns using timestamped evidence, explicit speaker attribution, published definitions, and human review.

## Research questions

- Which actors receive favourable, critical, neutral, mixed, or unclear coverage?
- Which actors are most frequently targeted by negative framing?
- Which voices receive airtime, quotation, or attribution?
- How much attention is given to protest demands, institutional response, policing, public disruption, politics, and allegations?
- Are headlines and thumbnails supported by the spoken content?
- Are allegations presented as allegations, questions, opinions, or established facts?
- How do framing patterns differ between outlets and programmes?

## Scope

This repository is limited to **media coverage of the NEET 2026 protests**.

It is not a general-purpose political monitoring repository, and it does not contain unrelated protest datasets.

See [SCOPE.md](SCOPE.md) for inclusion and exclusion rules.

## Core principles

1. **No predetermined side**
2. **Speaker attribution before outlet attribution**
3. **Evidence before scoring**
4. **Machine output is not a verified finding**
5. **Short public excerpts, not a public archive of broadcasts**
6. **Corrections remain visible**
7. **Methods and definitions are versioned**
8. **Comparable standards for all actors and outlets**

## Actor model

Coverage may target or favour any of the following:

- Protest organisers
- Individual protesters
- Students and candidates
- Parents
- Government representatives
- Exam and education authorities
- Police and security agencies
- Ruling-party representatives
- Opposition-party representatives
- Courts and public institutions
- Journalists, anchors, guests, and commentators
- Other actors directly relevant to the event

The system does not force all coverage into a simplistic two-side model.

## Evidence levels

| Tier | Meaning |
|---|---|
| A | Timestamped spoken evidence with verified source and speaker attribution |
| B | Exact official quotation or reliable attribution, but incomplete audiovisual verification |
| C | Headline, thumbnail, description, post, or other packaging evidence only |
| D | Mixed stream, unresolved identity, insufficient attribution, or unverified record |

Only reviewed Tier A and appropriately verified Tier B evidence should support strong public findings.

## Repository layout

```text
.
├── public-data/             # Publishable metadata, excerpts, annotations and metrics
├── private-workspace/       # Local-only audio, video and complete working transcripts
├── schemas/                 # Versioned evidence and analysis schemas
├── src/                     # Ingestion, validation and analysis code
├── dashboard/               # Public dashboard source
├── methodology/             # Taxonomy and scoring documentation
├── .github/                 # Validation workflows and contribution templates
├── SCOPE.md
├── METHODOLOGY.md
├── CORRECTIONS.md
└── CONTRIBUTING.md
```

## Public-data policy

The public repository may contain:

- Source URLs and video IDs
- Outlet and programme metadata
- Publication dates
- Exact timestamps
- Limited excerpts necessary to demonstrate a finding
- Project-created translations
- Speaker roles and verified identities where appropriate
- Human annotations
- Derived metrics
- Confidence and review status
- Correction history
- Transcript hashes and processing manifests

The public repository should not contain, by default:

- Downloaded broadcasts
- Downloaded audio
- Full subtitle files
- Complete third-party transcripts
- Authentication cookies
- API secrets
- Personal information about ordinary participants
- Machine-only accusations represented as confirmed facts

## Status

The repository is currently in the **methodology and data-normalisation phase**.

Initial work:

- Import the existing NEET 2026 media inventory
- Verify source URLs and outlet identities
- Separate packaging evidence from spoken evidence
- Build a timestamped evidence schema
- Establish a neutral framing taxonomy
- Create a human-review workflow
- Build a reproducible public dashboard

## Project disclaimer

This project analyses observable patterns in specific media items. It does not determine the private motives, honesty, ideology, or character of journalists, organisations, protesters, officials, or institutions.

Automated transcripts and classifications can contain errors. Named or high-severity findings require human review. Third-party media remains the property of its respective rights holders and is not licensed under this repository's open-source licences.

## Licences

- Source code: [Apache License 2.0](LICENSE)
- Original project documentation, annotations and derived public data: [CC BY 4.0](DATA_LICENSE.md)
- Third-party content: excluded from these licences unless explicitly stated
