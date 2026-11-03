#!/usr/bin/env python3
"""Fetch the latest publicly linked LME warehouse/queue XLSX without republishing it."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

SOURCE_PAGE = "https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports/Warehouse-and-queue-data"
USER_AGENT = "InstitutionalMarketIntelligence/1.0 (public LME report downloader)"
MAX_BYTES = 30 * 1024 * 1024


class ReportLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.href is not None:
            self.links.append((self.href, " ".join(" ".join(self.text).split())))
            self.href = None
            self.text = []


def request_bytes(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        final_url = response.geturl()
        if urlparse(final_url).hostname not in {"www.lme.com", "lme.com"}:
            raise RuntimeError(f"Unexpected download host: {urlparse(final_url).hostname}")
        content_type = response.headers.get("Content-Type", "")
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise RuntimeError("LME report exceeded the 30 MB safety limit.")
    return payload, content_type


def discover_latest_xlsx(html: str) -> tuple[str, str]:
    parser = ReportLinks()
    parser.feed(html)
    matches: list[tuple[str, str]] = []
    for href, label in parser.links:
        absolute = urljoin(SOURCE_PAGE, href)
        parsed = urlparse(absolute)
        if (
            parsed.hostname in {"www.lme.com", "lme.com"}
            and parsed.path.lower().endswith(".xlsx")
            and "warehouse-company-stocks-and-queue-data" in parsed.path.lower()
            and "warehouse company stocks and queue data" in label.lower()
        ):
            matches.append((absolute, label))
    if not matches:
        raise RuntimeError("No public Warehouse Company Stocks and Queue XLSX link was found on the official LME page.")
    return matches[0]


def inspect_workbook(path: Path) -> list[dict[str, object]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to inspect the downloaded workbook.") from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheets: list[dict[str, object]] = []
    try:
        for sheet in workbook.worksheets:
            preview = []
            for row in sheet.iter_rows(min_row=1, max_row=8, values_only=True):
                preview.append([None if value is None else str(value)[:160] for value in row[:20]])
            sheets.append({
                "name": sheet.title,
                "max_row": sheet.max_row,
                "max_column": sheet.max_column,
                "first_eight_rows_preview": preview,
            })
    finally:
        workbook.close()
    return sheets


def main() -> int:
    output = Path("lme-raw-output")
    output.mkdir(parents=True, exist_ok=True)

    page, _ = request_bytes(SOURCE_PAGE)
    report_url, report_label = discover_latest_xlsx(page.decode("utf-8", errors="replace"))
    raw, content_type = request_bytes(report_url)
    raw_path = output / Path(urlparse(report_url).path).name
    raw_path.write_bytes(raw)

    if not zipfile.is_zipfile(raw_path):
        raw_path.unlink(missing_ok=True)
        raise RuntimeError("The LME response was not a valid XLSX/ZIP file (it may require login or the page may have changed).")

    manifest = {
        "source": "London Metal Exchange",
        "report": report_label,
        "source_page": SOURCE_PAGE,
        "download_url": report_url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "content_type": content_type,
        "file_name": raw_path.name,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw_file_is_unmodified": True,
        "sheets": inspect_workbook(raw_path),
        "limitations": [
            "This is a monthly warehouse-company/queue report, not a live feed.",
            "The collector does not bypass account, access, or licensing controls.",
            "Raw report is stored only as a private workflow artifact; it is not committed to the public repository.",
            "No market signal is generated by this collector yet; workbook schema must be reviewed before mapping fields."
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("report", "file_name", "size_bytes", "sha256", "sheets")}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"LME raw collection failed: {error}", file=sys.stderr)
        raise SystemExit(1)
