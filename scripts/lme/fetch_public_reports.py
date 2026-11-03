#!/usr/bin/env python3
"""Inspect an LME report only when the official site grants access; never bypass access controls."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

SOURCE_PAGE = "https://www.lme.com/Market-data/Reports-and-data/Warehouse-and-stocks-reports/Warehouse-and-queue-data"
USER_AGENT = "InstitutionalMarketIntelligence/1.0 (LME report access checker)"
MAX_BYTES = 30 * 1024 * 1024
OUTPUT = Path("lme-raw-output")


class AccessRequired(Exception):
    def __init__(self, url: str, code: int):
        self.url = url
        self.code = code
        super().__init__(f"LME returned HTTP {code} for {url}")


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
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            final_url = response.geturl()
            if urlparse(final_url).hostname not in {"www.lme.com", "lme.com"}:
                raise RuntimeError(f"Unexpected LME download host: {urlparse(final_url).hostname}")
            content_type = response.headers.get("Content-Type", "")
            payload = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise AccessRequired(url, error.code) from error
        raise
    if len(payload) > MAX_BYTES:
        raise RuntimeError("LME report exceeded the 30 MB safety limit.")
    return payload, content_type


def discover_latest_xlsx(html: str) -> tuple[str, str]:
    parser = ReportLinks()
    parser.feed(html)
    for href, label in parser.links:
        absolute = urljoin(SOURCE_PAGE, href)
        parsed = urlparse(absolute)
        if (
            parsed.hostname in {"www.lme.com", "lme.com"}
            and parsed.path.lower().endswith(".xlsx")
            and "warehouse-company-stocks-and-queue-data" in parsed.path.lower()
            and "warehouse company stocks and queue data" in label.lower()
        ):
            return absolute, label
    raise RuntimeError("No matching Warehouse Company Stocks and Queue XLSX link was found; official page structure may have changed.")


def inspect_workbook(path: Path) -> list[dict[str, object]]:
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheets: list[dict[str, object]] = []
    try:
        for sheet in workbook.worksheets:
            header = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
            sheets.append({
                "name": sheet.title,
                "max_row": sheet.max_row,
                "max_column": sheet.max_column,
                "column_headers": [str(value).strip() if value is not None else "" for value in header[:40]],
            })
    finally:
        workbook.close()
    return sheets


def write_manifest(manifest: dict[str, object]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


def main() -> int:
    retrieved = datetime.now(timezone.utc).isoformat()
    try:
        page, _ = request_bytes(SOURCE_PAGE)
        report_url, report_label = discover_latest_xlsx(page.decode("utf-8", errors="replace"))
        raw, content_type = request_bytes(report_url)
    except AccessRequired as error:
        write_manifest({
            "source": "London Metal Exchange",
            "report_type": "Warehouse Company Stocks and Queue Data",
            "source_page": SOURCE_PAGE,
            "retrieved_at_utc": retrieved,
            "status": "REGISTERED_ACCESS_REQUIRED",
            "http_status": error.code,
            "blocked_url": error.url,
            "raw_file_fetched": False,
            "raw_file_retained": False,
            "message": "LME denied unauthenticated access. Sign in/register through the official LME account flow and use an authorized report export; this collector will not bypass access controls.",
            "next_step": "Use the existing LME XLSX import in the app for an authorized export, or configure an officially licensed access method after confirming its terms."
        })
        return 0

    with tempfile.TemporaryDirectory(prefix="lme-raw-") as temporary:
        raw_path = Path(temporary) / Path(urlparse(report_url).path).name
        raw_path.write_bytes(raw)
        if not zipfile.is_zipfile(raw_path):
            raise RuntimeError("LME response was not a valid XLSX/ZIP file.")
        sheets = inspect_workbook(raw_path)

    manifest = {
        "source": "London Metal Exchange",
        "report": report_label,
        "source_page": SOURCE_PAGE,
        "download_url": report_url,
        "retrieved_at_utc": retrieved,
        "status": "FETCHED_AND_INSPECTED",
        "content_type": content_type,
        "raw_file_name": Path(urlparse(report_url).path).name,
        "raw_file_size_bytes": len(raw),
        "raw_file_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_file_fetched": True,
        "raw_file_retained": False,
        "sheets": sheets,
        "limitations": [
            "Monthly warehouse-company/queue report; not a live feed.",
            "Raw workbook is processed in temporary storage and not committed or published.",
            "Signal calculations remain disabled until workbook columns and units are mapped and validated."
        ],
    }
    write_manifest(manifest)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"LME raw collection failed: {error}", file=sys.stderr)
        raise SystemExit(1)
