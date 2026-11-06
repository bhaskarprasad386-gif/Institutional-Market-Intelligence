#!/usr/bin/env python3
"""Fetch and archive NSE cash-market security-wise deliverable data.

This is a separate research input. It does not alter rollover signals or trading rules.
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://nsearchives.nseindia.com/products/content"
OUT_DIR = Path("public/data/nse-cash-delivery")
INDEX = OUT_DIR / "index.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/csv,application/octet-stream,*/*",
    "Referer": "https://www.nseindia.com/",
}


def norm(value):
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def pick(row, *names):
    lookup = {norm(key): value for key, value in row.items()}
    for name in names:
        value = lookup.get(norm(name))
        if value is not None and str(value).strip() not in ("", "-"):
            return str(value).strip()
    return ""


def number(value, field, allow_blank=False):
    raw = str(value or "").replace(",", "").strip()
    if not raw and allow_blank:
        return None
    try:
        result = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite {field}: {value!r}")
    return result


def parse_date(value):
    raw = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def parse_cash_delivery_csv(payload, expected_day):
    text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else str(payload)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Cash delivery CSV has no header")
    rows = []
    for raw in reader:
        series = pick(raw, "SERIES").upper()
        if series != "EQ":
            continue
        symbol = pick(raw, "SYMBOL")
        trade_date = parse_date(pick(raw, "DATE1", "DATE"))
        if not symbol or trade_date != expected_day.isoformat():
            continue
        traded = number(pick(raw, "TTL_TRD_QNTY", "TOTAL_TRADED_QUANTITY"), "traded quantity")
        # NSE occasionally publishes an EQ row with an empty DELIV_QTY.
        # Preserve the row and archive; null keeps downstream features partial.
        delivered = number(pick(raw, "DELIV_QTY", "DELIVERABLE_QTY"), "delivery quantity", allow_blank=True)
        # Some NSE rows also omit DELIV_PER. Keep the security/date row and
        # preserve the missing source value as null; never infer it from quantity.
        delivery_pct = number(
            pick(raw, "DELIV_PER", "DELIVERABLE_PERCENT"),
            "delivery percentage", allow_blank=True
        )
        close = number(pick(raw, "CLOSE_PRICE"), "close price")
        vwap = number(pick(raw, "AVG_PRICE", "VWAP"), "VWAP", allow_blank=True)
        trades = number(pick(raw, "NO_OF_TRADES"), "number of trades", allow_blank=True)
        if traded < 0 or (delivered is not None and (delivered < 0 or delivered > traded)):
            raise ValueError(f"Invalid delivery/traded quantities for {symbol}: {delivered}/{traded}")
        if delivery_pct is not None and (delivery_pct < 0 or delivery_pct > 100):
            raise ValueError(f"Invalid delivery percentage for {symbol}: {delivery_pct}")
        if close <= 0:
            raise ValueError(f"Invalid cash close for {symbol}: {close}")
        computed_pct = (
            delivered / traded * 100
            if delivered is not None and traded > 0 else None
        )
        # NSE's reported delivery percentage can differ from DELIV_QTY / traded
        # quantity on isolated rows. Preserve both source and computed values;
        # flag the discrepancy for downstream quality filtering instead of
        # discarding an otherwise valid trading date.
        pct_consistency = (
            "NOT_COMPUTABLE" if computed_pct is None or delivery_pct is None else
            "MATCH" if abs(computed_pct - delivery_pct) <= 1.0 else "MISMATCH"
        )
        rows.append({
            "symbol": symbol, "series": series, "tradeDate": trade_date,
            "closePrice": close, "vwap": vwap, "tradedQuantity": int(traded),
            "deliveryQuantity": int(delivered) if delivered is not None else None,
            "deliveryQuantityStatus": "AVAILABLE" if delivered is not None else "MISSING",
            "deliveryPct": delivery_pct,
            "deliveryPctStatus": "AVAILABLE" if delivery_pct is not None else "MISSING",
            "computedDeliveryPct": round(computed_pct, 4) if computed_pct is not None else None,
            "deliveryPctConsistencyStatus": pct_consistency,
            "tradeCount": int(trades) if trades is not None else None,
        })
    if not rows:
        raise ValueError(f"No valid EQ delivery rows found for {expected_day}")
    return rows


def fetch_for_date(day):
    filename = f"sec_bhavdata_full_{day.strftime('%d%m%Y')}.csv"
    url = f"{BASE}/{filename}"
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read()
    if not payload or payload.lstrip().startswith(b"<"):
        raise ValueError(f"NSE returned an invalid cash delivery response for {day}")
    rows = parse_cash_delivery_csv(payload, day)
    return filename, url, rows


def save_history(day, filename, url, rows):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "source": "NSE Full Bhavcopy and Security Deliverable Data",
        "sourceUrl": url, "fileName": filename, "marketDate": day.isoformat(),
        "retrievedAt": retrieved, "rowCount": len(rows), "rows": rows,
    }
    (OUT_DIR / f"{day.isoformat()}.json").write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    dates = sorted(path.stem for path in OUT_DIR.glob("????-??-??.json") if len(path.stem) == 10)
    INDEX.write_text(json.dumps({
        "source": "NSE Full Bhavcopy and Security Deliverable Data",
        "updatedAt": retrieved, "count": len(dates),
        "dates": [{"marketDate": date, "path": f"{date}.json"} for date in reversed(dates)],
    }, separators=(",", ":")), encoding="utf-8")
    print(f"Archived cash delivery {day}: {len(rows)} EQ securities")


def backfill_existing_fo_dates():
    fo_index = Path("public/data/nse-fo-history/index.json")
    if not fo_index.exists():
        raise SystemExit("F&O history index is missing; run the F&O historical backfill first.")
    index = json.loads(fo_index.read_text(encoding="utf-8"))
    dates = sorted({dt.date.fromisoformat(item["marketDate"]) for item in index.get("dates", [])})
    if not dates:
        raise SystemExit("F&O history index contains no trading dates.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    successes = skipped = failed = 0
    for day in dates:
        target = OUT_DIR / f"{day.isoformat()}.json"
        if target.exists() and target.stat().st_size > 100:
            skipped += 1
            continue
        try:
            filename, url, rows = fetch_for_date(day)
            save_history(day, filename, url, rows)
            successes += 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            failed += 1
            print(f"SKIP {day}: {exc}")
        time.sleep(1)
    print(f"Cash delivery backfill complete: {successes} fetched, {skipped} already archived, {failed} failed.")
    ensure_backfill_complete(successes, skipped, failed)


def ensure_backfill_complete(successes, skipped, failed):
    """Fail visibly on partial coverage; successful files remain resumable."""
    if failed:
        raise SystemExit(
            f"Cash delivery backfill incomplete: {failed} dates failed; "
            f"{successes} fetched and {skipped} already archived. "
            "Successful dates are preserved; rerun to retry missing dates."
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill-existing-fo-dates", action="store_true")
    args = parser.parse_args()
    if args.backfill_existing_fo_dates:
        backfill_existing_fo_dates()
        return
    today = dt.datetime.now(dt.timezone.utc).date()
    errors = []
    for offset in range(8):
        day = today - dt.timedelta(days=offset)
        # The scheduled daily job must be idempotent: once the latest available
        # trading date is archived, stop instead of rewriting retrievedAt daily.
        existing = OUT_DIR / f"{day.isoformat()}.json"
        if existing.exists() and existing.stat().st_size > 100:
            print(f"Latest available cash delivery date already archived: {day}")
            return
        try:
            filename, url, rows = fetch_for_date(day)
            save_history(day, filename, url, rows)
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            errors.append(f"{day.isoformat()}: {exc}")
            time.sleep(1)
    raise SystemExit("Unable to fetch NSE cash delivery report:
" + "
".join(errors))

if __name__ == "__main__":
    main()
