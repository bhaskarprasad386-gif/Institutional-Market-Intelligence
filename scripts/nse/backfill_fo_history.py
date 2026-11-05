#!/usr/bin/env python3
"""Backfill NSE equity F&O futures bhavcopy history without changing latest data."""
import argparse
import csv
import datetime as dt
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from fetch_fo_bhavcopy import BASE as UDIFF_BASE, HEADERS, fetch_for_date

LEGACY_BASE = "https://archives.nseindia.com/content/historical/DERIVATIVES"
HISTORY_DIR = Path("public/data/nse-fo-history")
UDIFF_START = dt.date(2024, 7, 8)


def value(row, *names):
    lookup = {str(k).strip().upper(): v for k, v in row.items()}
    for name in names:
        found = lookup.get(name.upper())
        if found is not None and str(found).strip() not in ("", "-"):
            return str(found).strip()
    return ""


def parse_day(raw):
    raw = str(raw or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def fetch_legacy(day):
    month = day.strftime("%b").upper()
    filename = f"fo{day.strftime('%d')}{month}{day.strftime('%Y')}bhav.csv.zip"
    url = f"{LEGACY_BASE}/{day.year}/{month}/{filename}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as response:
        payload = response.read()
    if not payload.startswith(b"PK"):
        raise ValueError(f"Legacy NSE response is not ZIP for {day}")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError(f"No CSV in legacy archive for {day}")
        with archive.open(names[0]) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
            rows = []
            for raw in reader:
                instrument = value(raw, "INSTRUMENT").upper()
                if instrument not in {"FUTIDX", "FUTSTK"}:
                    continue
                trade_date = parse_day(value(raw, "TIMESTAMP", "TRADE_DATE", "DATE"))
                expiry = parse_day(value(raw, "EXPIRY_DT", "EXPIRY_DATE"))
                symbol = value(raw, "SYMBOL")
                settle = value(raw, "SETTLE_PR", "SETTLEMENT_PRICE")
                oi = value(raw, "OPEN_INT", "OPEN_INTEREST")
                if not (symbol and trade_date == day.isoformat() and expiry and settle and oi):
                    continue
                rows.append({
                    "symbol": symbol, "tradeDate": trade_date, "expiryDate": expiry,
                    "instrumentType": instrument, "futuresClose": settle,
                    "spotClose": value(raw, "UNDERLYING_VALUE", "UNDERLYING_PRICE") or "0",
                    "openInterest": oi,
                    "changeOpenInterest": value(raw, "CHG_IN_OI", "CHANGE_IN_OI"),
                    "previousFuturesClose": value(raw, "PREV_CLOSE", "PREV_CL_PR"),
                    "volume": value(raw, "CONTRACTS"),
                })
    if not rows:
        raise ValueError(f"No valid legacy futures rows for {day}; schema/date may differ")
    return filename, rows


def save_history(day, filename, rows):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    target = HISTORY_DIR / f"{day.isoformat()}.json"
    payload = {
        "source": "NSE F&O historical bhavcopy (UDiFF)" if day >= UDIFF_START else "NSE F&O historical bhavcopy (legacy)",
        "sourceUrl": f"{UDIFF_BASE}/{filename}" if day >= UDIFF_START else f"{LEGACY_BASE}/{day.year}/{day.strftime('%b').upper()}/{filename}",
        "fileName": filename, "marketDate": day.isoformat(),
        "retrievedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rowCount": len(rows), "rows": rows,
    }
    target.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    existing = sorted(p.stem for p in HISTORY_DIR.glob("????-??-??.json") if len(p.stem) == 10)
    index = {
        "source": "NSE F&O UDiFF + legacy daily bhavcopy archive",
        "updatedAt": payload["retrievedAt"], "count": len(existing),
        "dates": [{"marketDate": d, "path": f"{d}.json"} for d in reversed(existing)],
    }
    (HISTORY_DIR / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    print(f"Archived {day}: {len(rows)} futures rows")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD, inclusive")
    args = parser.parse_args()
    start = dt.date.fromisoformat(args.start_date)
    end = dt.date.fromisoformat(args.end_date)
    if end < start:
        raise SystemExit("end-date must be on or after start-date")
    if (end - start).days > 30:
        raise SystemExit("Maximum 31 calendar days per run; use smaller batches")
    if end >= UDIFF_START and start < UDIFF_START:
        print("Date range crosses the NSE 8-Jul-2024 format boundary; both parsers will be used.")
    successes = skipped = 0
    for offset in range((end - start).days + 1):
        day = start + dt.timedelta(days=offset)
        try:
            if day >= UDIFF_START:
                filename, rows = fetch_for_date(day)
            else:
                filename, rows = fetch_legacy(day)
            if not rows or any(r["tradeDate"] != day.isoformat() for r in rows):
                raise ValueError("Downloaded data failed trade-date validation")
            for row in rows:
                try:
                    settlement = float(str(row["futuresClose"]).replace(",", ""))
                    open_interest = float(str(row["openInterest"]).replace(",", ""))
                    expiry = dt.date.fromisoformat(row["expiryDate"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid futures settlement/OI/expiry row: {exc}") from exc
                if settlement <= 0 or open_interest < 0 or expiry < day:
                    raise ValueError("Futures row has non-positive settlement, negative OI, or expiry before trade date")
            save_history(day, filename, rows)
            successes += 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, zipfile.BadZipFile, KeyError) as exc:
            skipped += 1
            print(f"SKIP {day}: {exc}")
        time.sleep(1.0)
    print(f"Backfill complete: {successes} archived sessions, {skipped} skipped dates")
    if successes == 0:
        raise SystemExit("No sessions were archived; existing history was left unchanged.")


if __name__ == "__main__":
    main()
