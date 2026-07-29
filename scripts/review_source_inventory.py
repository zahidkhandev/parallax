#!/usr/bin/env python3
"""One-shot eligibility review for the 2026-07-29 source inventory.

This script performs source inclusion review only. It deliberately does not infer
stance, framing, favourability, criticism, neutrality, or bias.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from googlenewsdecoder import gnewsdecoder

REPORT_START = datetime.fromisoformat("2026-07-01T00:00:00+00:00")
REPORT_END_DATE = datetime.fromisoformat("2026-07-29T23:59:59+00:00").date()
REVIEW_DATE = "2026-07-29"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/126.0 Safari/537.36 Project-Parallax/1.0"
)
TRACKING_KEYS = {
    "oc",
    "hl",
    "gl",
    "ceid",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}

PROTEST_TERMS = (
    "protest",
    "protests",
    "protester",
    "protestor",
    "demonstration",
    "march",
    "agitation",
    "dharna",
    "sit-in",
    "rally",
    "hunger strike",
    "jantar mantar",
    "cockroach janta party",
    "cjp",
    "abhijeet dipke",
    "sonam wangchuk",
    "police action",
    "police excess",
    "lathi",
    "pellet gun",
    "detained",
    "detention",
    "crackdown",
    "stir",
    "bandh",
    "morcha",
    "विरोध",
    "प्रदर्शन",
    "आंदोलन",
    "धरना",
    "मार्च",
    "रैली",
    "भूख हड़ताल",
    "लाठीचार्ज",
    "हिरासत",
    "जंतर मंतर",
)
NEET_TERMS = ("neet", "नीट")
OTHER_EVENT_MARKERS = (
    "fmge",
    "psc protest",
    "teacher protest",
    "farmers protest",
    "railway protest",
    "ssc protest",
    "upsc protest",
)
VIDEO_TITLE_MARKERS = ("video |", "video:", "watch:", "watch |", "वीडियो", "देखें वीडियो")
INTERVIEW_MARKERS = ("interview", "q&a", "speaks to", "in conversation", "exclusive conversation")


@dataclass
class PageObservation:
    requested_url: str
    final_url: str | None
    canonical_url: str | None
    availability: str
    status_code: int | None
    title: str | None
    outlet: str | None
    published_at: str | None
    language: str | None
    media_format: str | None
    text: str
    note: str | None


def compact(value: str | None, limit: int = 1000) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] or None


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in TRACKING_KEYS],
        doseq=True,
    )
    path = re.sub(r"/amp/?$", "/", parts.path, flags=re.IGNORECASE)
    path = re.sub(r"//+", "/", path)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def decode_google_news_url(url: str) -> tuple[str | None, str | None]:
    if "news.google.com" not in urlsplit(url).netloc.lower():
        return normalize_url(url), None
    try:
        result = gnewsdecoder(url, interval=0.05)
        if result.get("status") and result.get("decoded_url"):
            return normalize_url(str(result["decoded_url"])), None
        return None, compact(str(result.get("message") or "Google News URL could not be decoded."), 300)
    except Exception as exc:  # noqa: BLE001 - preserve unresolved records
        return None, compact(f"Google News URL decode failed: {exc}", 300)


def meta_content(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str | None:
    for attribute, value in selectors:
        tag = soup.find("meta", attrs={attribute: value})
        if tag and tag.get("content"):
            return compact(str(tag["content"]), 1000)
    return None


def iter_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            payload = json.loads(tag.string or tag.get_text(" ", strip=True))
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        while candidates:
            candidate = candidates.pop()
            if not isinstance(candidate, dict):
                continue
            objects.append(candidate)
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                candidates.extend(graph)
    return objects


def parse_publisher_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.isoformat()


def detect_language(soup: BeautifulSoup, title: str | None, text: str) -> str | None:
    html = soup.find("html")
    if html and html.get("lang"):
        lang = str(html.get("lang")).strip().replace("_", "-")
        if re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*", lang):
            primary = lang.split("-", 1)[0].lower()
            if primary in {"en", "hi"}:
                return primary
    sample = f"{title or ''} {text[:5000]}"
    devanagari = len(re.findall(r"[\u0900-\u097F]", sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    if devanagari > max(25, latin * 0.25):
        return "hi"
    if latin > 20:
        return "en"
    return None


def detect_media_format(url: str, title: str | None, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str:
    lowered_title = (title or "").lower()
    lowered_url = url.lower()
    schema_types = {str(obj.get("@type", "")).lower() for obj in json_ld}
    has_video = bool(soup.find("video")) or "videoobject" in schema_types or any(
        key in lowered_url for key in ("/video/", "/videos/", "youtube.com/", "youtu.be/")
    )
    if "live" in lowered_title and has_video:
        return "live_stream"
    if any(marker in lowered_title for marker in INTERVIEW_MARKERS):
        return "interview"
    if has_video and (
        any(marker in lowered_title for marker in VIDEO_TITLE_MARKERS)
        or any(key in lowered_url for key in ("/video/", "/videos/", "youtube.com/", "youtu.be/"))
    ):
        return "digital_video"
    article_types = {"newsarticle", "article", "reportagenewsarticle"}
    if has_video and schema_types.intersection(article_types):
        return "article_with_video"
    return "other_news_media"


def observe_page(url: str, session: requests.Session) -> PageObservation:
    try:
        response = session.get(url, timeout=(15, 30), allow_redirects=True)
    except requests.RequestException as exc:
        return PageObservation(url, None, None, "unknown", None, None, None, None, None, None, "", compact(str(exc), 300))

    status = response.status_code
    final_url = normalize_url(response.url)
    if status == 451:
        return PageObservation(url, final_url, final_url, "geo_restricted", status, None, None, None, None, None, "", "Publisher returned HTTP 451.")
    if status in {404, 410}:
        return PageObservation(url, final_url, final_url, "unavailable", status, None, None, None, None, None, "", f"Publisher returned HTTP {status}.")
    if status in {401, 403, 429} or status >= 500:
        return PageObservation(url, final_url, final_url, "unknown", status, None, None, None, None, None, "", f"Publisher returned HTTP {status}; content could not be verified.")
    if not 200 <= status < 400:
        return PageObservation(url, final_url, final_url, "unknown", status, None, None, None, None, None, "", f"Unexpected HTTP {status}.")

    soup = BeautifulSoup(response.text, "html.parser")
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in str(value).lower())
    canonical = final_url
    if canonical_tag and canonical_tag.get("href"):
        canonical = normalize_url(urljoin(final_url, str(canonical_tag["href"])))

    json_ld = iter_json_ld(soup)
    title = meta_content(soup, ("property", "og:title"), ("name", "twitter:title"))
    if not title:
        for obj in json_ld:
            if obj.get("headline"):
                title = compact(str(obj["headline"]), 500)
                break
    if not title and soup.title:
        title = compact(soup.title.get_text(" ", strip=True), 500)

    outlet = meta_content(soup, ("property", "og:site_name"), ("name", "application-name"))
    if not outlet:
        for obj in json_ld:
            publisher = obj.get("publisher")
            if isinstance(publisher, dict) and publisher.get("name"):
                outlet = compact(str(publisher["name"]), 200)
                break

    date_candidates = [
        meta_content(
            soup,
            ("property", "article:published_time"),
            ("name", "date"),
            ("name", "pubdate"),
            ("name", "publish-date"),
            ("itemprop", "datePublished"),
        )
    ]
    for obj in json_ld:
        date_candidates.extend([obj.get("datePublished"), obj.get("dateCreated")])
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        date_candidates.append(time_tag.get("datetime"))
    published_at = next((parsed for value in date_candidates if (parsed := parse_publisher_date(str(value) if value else None))), None)

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = compact(soup.get_text(" ", strip=True), 30000) or ""
    language = detect_language(soup, title, text)
    media_format = detect_media_format(canonical, title, soup, json_ld)
    return PageObservation(
        url,
        final_url,
        canonical,
        "available",
        status,
        title,
        outlet,
        published_at,
        language,
        media_format,
        text,
        None,
    )


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def classify(record: dict[str, Any], observation: PageObservation) -> tuple[str, str | None, str]:
    if observation.availability != "available":
        return "pending_review", None, "Publisher content was inaccessible, so event connection and publication metadata remain unresolved."
    if not observation.published_at:
        return "pending_review", None, "Publisher page did not expose a timezone-aware publication timestamp; the collection-window check remains unresolved."

    published = date_parser.parse(observation.published_at)
    if published.date() < REPORT_START.date():
        return "excluded", "Publisher date is before 1 July 2026, outside the declared collection window.", "Publication date verified outside the collection window."
    if published.date() > REPORT_END_DATE:
        return "excluded", "Publisher date is after the 29 July 2026 report-through date, outside the declared collection window.", "Publication date verified outside the collection window."

    combined = " ".join(
        part for part in (observation.title, record.get("title"), observation.text[:20000]) if part
    )
    has_neet = contains_any(combined, NEET_TERMS)
    has_event = contains_any(combined, PROTEST_TERMS)
    if has_neet and has_event:
        return "included", None, "Publisher page connects the item to the defined NEET 2026 protest event and collection window."
    if contains_any(combined, OTHER_EVENT_MARKERS) and not has_neet:
        return "excluded", "Concerns a different examination or protest event, not the defined NEET 2026 protests.", "Publisher page identifies a different event."
    if has_neet and not has_event:
        return "excluded", "Reports on NEET 2026 examination administration, results, counselling, or another generic NEET issue without a substantive connection to the defined protests.", "Publisher page lacks a substantive protest-event connection."
    return "excluded", "Does not concern the defined NEET 2026 protests.", "Publisher page does not establish the required event connection."


def review_record(record: dict[str, Any], session: requests.Session) -> dict[str, Any]:
    decoded_url, decode_note = decode_google_news_url(str(record["source_url"]))
    if not decoded_url:
        updated = dict(record)
        updated["availability"] = "unknown"
        updated["eligibility"] = "pending_review"
        updated["exclusion_reason"] = None
        updated["notes"] = compact(
            f"Eligibility review attempted {REVIEW_DATE}; original publisher URL could not be resolved. {decode_note or ''} No stance review performed.",
            1000,
        )
        return updated

    observation = observe_page(decoded_url, session)
    eligibility, exclusion_reason, review_note = classify(record, observation)
    updated = dict(record)
    updated["source_url"] = observation.canonical_url or decoded_url
    updated["availability"] = observation.availability
    updated["eligibility"] = eligibility
    updated["exclusion_reason"] = exclusion_reason
    if observation.title:
        updated["title"] = observation.title[:500]
    if observation.outlet:
        updated["outlet"] = observation.outlet[:200]
    if observation.published_at:
        updated["published_at"] = observation.published_at
    if observation.language:
        updated["original_language"] = observation.language
    if observation.media_format:
        updated["media_format"] = observation.media_format
    details = [
        f"Eligibility review performed {REVIEW_DATE} from publisher metadata and page text.",
        review_note,
        f"HTTP {observation.status_code}." if observation.status_code else None,
        observation.note,
        decode_note,
        "No stance or framing classification performed.",
    ]
    updated["notes"] = compact(" ".join(item for item in details if item), 1000)
    return updated


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    order: list[str] = []
    for record in records:
        key = normalize_url(str(record["source_url"]))
        if key not in grouped:
            order.append(key)
        grouped[key].append(record)

    output: list[dict[str, Any]] = []
    priority = {"included": 0, "excluded": 1, "pending_review": 2}
    for key in order:
        group = grouped[key]
        if len(group) == 1:
            output.append(group[0])
            continue
        group.sort(key=lambda item: (priority.get(str(item["eligibility"]), 9), str(item["source_id"])))
        kept = group[0]
        duplicate_ids = [str(item["source_id"]) for item in group[1:]]
        queries = sorted({str(item.get("discovery_query")) for item in group if item.get("discovery_query")})
        suffix = (
            f" Canonical duplicate consolidation: kept one publisher URL for {len(group)} discoveries; "
            f"removed source IDs {', '.join(duplicate_ids[:12])}"
            f"{' and others' if len(duplicate_ids) > 12 else ''}. Discovery queries: {'; '.join(queries[:8])}."
        )
        kept["notes"] = compact((kept.get("notes") or "") + suffix, 1000)
        output.append(kept)
    return output


def write_audit(records: list[dict[str, Any]], path: Path) -> None:
    def counts(field: str) -> dict[str, int]:
        values: dict[str, int] = defaultdict(int)
        for record in records:
            values[str(record[field])] += 1
        return dict(sorted(values.items()))

    included = [record for record in records if record["eligibility"] == "included"]
    included_outlets: dict[str, int] = defaultdict(int)
    for record in included:
        included_outlets[str(record["outlet"])] += 1
    audit = {
        "inventory_audit_version": "1.0.0",
        "source_count": len(records),
        "included_count": len(included),
        "excluded_count": sum(record["eligibility"] == "excluded" for record in records),
        "pending_count": sum(record["eligibility"] == "pending_review" for record in records),
        "by_eligibility": counts("eligibility"),
        "by_availability": counts("availability"),
        "by_media_format": counts("media_format"),
        "by_language": counts("original_language"),
        "included_by_outlet": dict(sorted(included_outlets.items())),
        "notes": [
            "Inventory inclusion is independent of expected stance or finding direction.",
            "Counts describe discovered sources and do not measure outlet quality or bias.",
            "Eligibility review was based on publisher metadata and page text; unresolved access or metadata remained pending.",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=Path("public-data/source-inventory.jsonl"))
    parser.add_argument("--audit", type=Path, default=Path("build/inventory-audit.json"))
    parser.add_argument("--limit", type=int, default=None, help="Optional development limit")
    args = parser.parse_args()

    records = [json.loads(line) for line in args.inventory.read_text(encoding="utf-8").splitlines() if line.strip()]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8"})

    reviewed: list[dict[str, Any]] = []
    for index, record in enumerate(records, 1):
        if args.limit is not None and index > args.limit:
            reviewed.append(record)
            continue
        if record.get("eligibility") == "pending_review":
            reviewed.append(review_record(record, session))
        else:
            reviewed.append(record)
        if index % 25 == 0:
            print(f"Reviewed {index}/{len(records)} candidates", flush=True)
            time.sleep(0.1)

    reviewed = deduplicate(reviewed)
    args.inventory.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in reviewed),
        encoding="utf-8",
    )
    write_audit(reviewed, args.audit)
    print(
        json.dumps(
            {
                "source_count": len(reviewed),
                "included": sum(record["eligibility"] == "included" for record in reviewed),
                "excluded": sum(record["eligibility"] == "excluded" for record in reviewed),
                "pending": sum(record["eligibility"] == "pending_review" for record in reviewed),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
