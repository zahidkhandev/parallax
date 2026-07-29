#!/usr/bin/env python3
"""Run the one-shot source eligibility review with conservative safeguards.

The underlying reviewer resolves and observes publisher pages. This runner adds
parallel execution, retries, and a stricter event-connection test that avoids
including generic NEET pages merely because navigation or related-story modules
mention a protest. It performs no stance or framing analysis.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from dateutil import parser as date_parser

from scripts import review_source_inventory as base

INVENTORY = Path("public-data/source-inventory.jsonl")
AUDIT = Path("build/inventory-audit.json")
MAX_WORKERS = 4

CORE_EVENT_TERMS = (
    "jantar mantar",
    "cockroach janta party",
    "cjp",
    "abhijeet dipke",
    "sonam wangchuk",
    "paper leak protest",
    "police excess",
    "police action",
    "pellet gun",
    "lathi charge",
    "lathi-charge",
    "sansad chalo",
    "parliament march",
    "जंतर मंतर",
    "अभिजीत",
    "सोनम वांगचुक",
    "लाठीचार्ज",
)
GENERIC_PROTEST_PATTERNS = (
    r"\bprotests?\b",
    r"\bprotesters?\b",
    r"\bprotestors?\b",
    r"\bdemonstrations?\b",
    r"\bagitation\b",
    r"\bdharna\b",
    r"\bsit[- ]in\b",
    r"\brall(?:y|ies)\b",
    r"\bhunger strike\b",
    r"\bdetain(?:ed|s|ing|ment)?\b",
    r"\bcrackdown\b",
    r"\bbandh\b",
    r"\bmorcha\b",
    r"विरोध",
    r"प्रदर्शन",
    r"आंदोलन",
    r"धरना",
    r"रैली",
    r"भूख हड़ताल",
    r"हिरासत",
)


def contains_neet(text: str) -> bool:
    return bool(re.search(r"\bneet(?:-ug)?\b|नीट", text, re.IGNORECASE))


def contains_core_event(text: str) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in CORE_EVENT_TERMS)


def protest_occurrences(text: str) -> int:
    return sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in GENERIC_PROTEST_PATTERNS)


def hardened_classify(
    record: dict[str, Any], observation: base.PageObservation
) -> tuple[str, str | None, str]:
    if observation.availability != "available":
        return (
            "pending_review",
            None,
            "Publisher content was inaccessible, so event connection and publication metadata remain unresolved.",
        )
    if not observation.published_at:
        return (
            "pending_review",
            None,
            "Publisher page did not expose a timezone-aware publication timestamp; the collection-window check remains unresolved.",
        )

    published = date_parser.parse(observation.published_at)
    if published.date() < base.REPORT_START.date():
        return (
            "excluded",
            "Publisher date is before 1 July 2026, outside the declared collection window.",
            "Publication date verified outside the collection window.",
        )
    if published.date() > base.REPORT_END_DATE:
        return (
            "excluded",
            "Publisher date is after the 29 July 2026 report-through date, outside the declared collection window.",
            "Publication date verified outside the collection window.",
        )

    publisher_title = observation.title or ""
    discovered_title = str(record.get("title") or "")
    title = f"{publisher_title} {discovered_title}".strip()
    body = observation.text[:7000]

    title_has_neet = contains_neet(title)
    title_has_core = contains_core_event(title)
    title_protest_count = protest_occurrences(title)
    body_has_neet = contains_neet(body)
    body_has_core = contains_core_event(body)
    body_protest_count = protest_occurrences(body)

    if base.contains_any(title, base.OTHER_EVENT_MARKERS) and not title_has_neet:
        return (
            "excluded",
            "Concerns a different examination or protest event, not the defined NEET 2026 protests.",
            "Publisher title identifies a different event.",
        )

    # A publisher title that explicitly joins NEET with the protest event is
    # sufficient. Core event actors/locations may appear without NEET in the
    # title, but the article body must then establish the NEET connection.
    if title_has_neet and (title_has_core or title_protest_count > 0):
        return (
            "included",
            None,
            "Publisher title explicitly connects the item to the defined NEET 2026 protest event.",
        )
    if title_has_core and body_has_neet:
        return (
            "included",
            None,
            "Publisher title identifies the protest event and the article body confirms its NEET 2026 connection.",
        )

    # For titles that are not explicit, require substantive body treatment,
    # not one incidental contextual mention or a related-story link.
    if body_has_neet and body_has_core and body_protest_count > 0:
        return (
            "included",
            None,
            "Publisher article body substantively connects the item to the defined NEET 2026 protest event.",
        )
    if title_has_neet and body_has_neet and body_protest_count >= 3:
        return (
            "included",
            None,
            "Publisher article body contains sustained coverage of the NEET 2026 protests.",
        )

    combined = f"{title} {body}"
    if contains_neet(combined):
        return (
            "excluded",
            "Reports on NEET 2026 examination administration, results, counselling, or another generic NEET issue without a substantive connection to the defined protests.",
            "Publisher page lacks a substantive protest-event connection.",
        )
    return (
        "excluded",
        "Does not concern the defined NEET 2026 protests.",
        "Publisher page does not establish the required event connection.",
    )


_original_decode = base.decode_google_news_url


def decode_with_retry(url: str) -> tuple[str | None, str | None]:
    last: tuple[str | None, str | None] = (None, None)
    for attempt in range(3):
        last = _original_decode(url)
        if last[0]:
            return last
        time.sleep(0.75 * (attempt + 1))
    return last


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": base.USER_AGENT,
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        }
    )
    return session


def review_one(index: int, record: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if record.get("eligibility") != "pending_review":
        return index, record
    session = make_session()
    try:
        return index, base.review_record(record, session)
    finally:
        session.close()


def main() -> int:
    base.classify = hardened_classify
    base.decode_google_news_url = decode_with_retry

    records = [
        json.loads(line)
        for line in INVENTORY.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reviewed: list[dict[str, Any] | None] = [None] * len(records)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(review_one, index, record): index
            for index, record in enumerate(records)
        }
        completed = 0
        for future in as_completed(futures):
            index, result = future.result()
            reviewed[index] = result
            completed += 1
            if completed % 25 == 0 or completed == len(records):
                print(f"Reviewed {completed}/{len(records)} candidates", flush=True)

    final_records = base.deduplicate([record for record in reviewed if record is not None])
    INVENTORY.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in final_records
        ),
        encoding="utf-8",
    )
    base.write_audit(final_records, AUDIT)
    summary = {
        "source_count": len(final_records),
        "included": sum(record["eligibility"] == "included" for record in final_records),
        "excluded": sum(record["eligibility"] == "excluded" for record in final_records),
        "pending": sum(record["eligibility"] == "pending_review" for record in final_records),
        "languages": {
            language: sum(record["original_language"] == language for record in final_records)
            for language in sorted({str(record["original_language"]) for record in final_records})
        },
        "formats": {
            media_format: sum(record["media_format"] == media_format for record in final_records)
            for media_format in sorted({str(record["media_format"]) for record in final_records})
        },
        "availability": {
            availability: sum(record["availability"] == availability for record in final_records)
            for availability in sorted({str(record["availability"]) for record in final_records})
        },
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
