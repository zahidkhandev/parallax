"""Deterministic structural accessibility checks for generated HTML reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class AccessibilityCheck:
    """One machine-readable structural report check."""

    name: str
    passed: bool
    detail: str


class _ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.title_depth = 0
        self.title_text: list[str] = []
        self.main_count = 0
        self.h1_count = 0
        self.ids: list[str] = []
        self.controls: list[tuple[str, str]] = []
        self.label_for: set[str] = set()
        self.label_depth = 0
        self.external_resources: list[str] = []
        self.images_without_alt = 0
        self.tables = 0
        self.table_headers = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.html_lang = attributes.get("lang") or ""
        elif tag == "title":
            self.title_depth += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "label":
            self.label_depth += 1
            if attributes.get("for"):
                self.label_for.add(attributes["for"])
        elif tag in {"input", "select", "textarea"}:
            self.controls.append((attributes.get("id") or "", tag if self.label_depth else ""))
        elif tag == "img" and "alt" not in attributes:
            self.images_without_alt += 1
        elif tag == "table":
            self.tables += 1
        elif tag == "th":
            self.table_headers += 1
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        if tag in {"script", "link", "img", "iframe"}:
            resource = attributes.get("src") or attributes.get("href")
            if resource and (resource.startswith("http://") or resource.startswith("https://")):
                self.external_resources.append(resource)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.title_depth -= 1
        elif tag == "label":
            self.label_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_text.append(data)


def audit_html_text(content: str) -> dict[str, object]:
    """Audit report-level accessibility invariants without network dependencies."""
    parser = _ReportParser()
    parser.feed(content)
    duplicate_ids = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    unlabeled = [
        control_id or "(missing id)"
        for control_id, nested_label in parser.controls
        if not nested_label and control_id not in parser.label_for
    ]
    checks = (
        AccessibilityCheck("document_language", bool(parser.html_lang.strip()), "html has lang"),
        AccessibilityCheck(
            "document_title",
            bool("".join(parser.title_text).strip()),
            "title is nonempty",
        ),
        AccessibilityCheck("single_main", parser.main_count == 1, f"found {parser.main_count}"),
        AccessibilityCheck("single_h1", parser.h1_count == 1, f"found {parser.h1_count}"),
        AccessibilityCheck("unique_ids", not duplicate_ids, f"duplicates: {duplicate_ids}"),
        AccessibilityCheck("labelled_controls", not unlabeled, f"unlabelled: {unlabeled}"),
        AccessibilityCheck(
            "image_alternatives",
            parser.images_without_alt == 0,
            f"missing alt: {parser.images_without_alt}",
        ),
        AccessibilityCheck(
            "table_headers",
            parser.tables == 0 or parser.table_headers > 0,
            f"{parser.tables} table(s), {parser.table_headers} header(s)",
        ),
        AccessibilityCheck(
            "self_contained",
            not parser.external_resources,
            f"external resources: {parser.external_resources}",
        ),
    )
    return {
        "audit_version": "1.0.0",
        "passed": all(check.passed for check in checks),
        "checks": [asdict(check) for check in checks],
    }


def audit_html(path: Path) -> dict[str, object]:
    """Read and audit one UTF-8 report file."""
    return audit_html_text(path.read_text(encoding="utf-8"))
