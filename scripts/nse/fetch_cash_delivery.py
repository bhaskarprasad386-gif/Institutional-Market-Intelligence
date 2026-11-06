#!/usr/bin/env python3
"""Fetch and archive NSE cash-market security-wise deliverable data.

This is a separate research input. It does not alter rollover signals or trading rules.
"""
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
        delivered = number(pick(raw, "DELIV_QTY", "DELIVERABLE_QTY"), "delivery quantity")
        delivery_pct = number(pick(raw, "DELIV_PER", "DELIVERABLE_PERCENT"), "delivery percentage")
        close = number(pick(raw, "CLOSE_PRICE"), "close price")
        vwap = number(pick(raw, "AVG_PRICE", "VWAP"), "VWAP", allow_blank=True)
        trades = number(pick(raw, "NO_OF_TRADES"), "number of trades", allow_blank=True)
        if traded < 0 or delivered < 0 or delivered > traded:
            raise ValueError(f"Invalid delivery/traded quantities for {symbol}: {delivered}/{traded}")
        if delivery_pct < 0 or delivery_pct > 100:
            raise ValueError(f"Invalid delivery percentage for {symbol}: {delivery_pct}")
        if close <= 0:
            raise ValueError(f"Invalid cash close for {symbol}: {close}")
        computed_pct = delivered / traded * 100 if traded else None
        if computed_pct is not None and abs(computed_pct - delivery_pct) > 1.0:
            raise ValueError(f"Reported and computed delivery percentage disagree for {symbol}")
        rows.append({
            "symbol": symbol, "series": series, "tradeDate": trade_date,
            "closePrice": close, "vwap": vwap, "tradedQuantity": int(traded),
            "deliveryQuantity": int(delivered), "deliveryPct": delivery_pct,
            "computedDeliveryPct": round(computed_pct, 4) if computed_pct is not None else None,
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


def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    errors = []
    for offset in range(8):
        day = today - dt.timedelta(days=offset)
        try:
            filename, url, rows = fetch_for_date(day)
            save_history(day, filename, url, rows)
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            errors.append(f"{day.isoformat()}: {exc}")
            time.sleep(1)
    raise SystemExit("Unable to fetch NSE cash delivery report:\n" + "\n".join(errors))


if __name__ == "__main__":
    main()
