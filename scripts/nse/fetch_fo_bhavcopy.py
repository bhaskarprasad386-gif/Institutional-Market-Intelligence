#!/usr/bin/env python3
"""Fetch the official NSE F&O UDiFF EOD bhavcopy and publish normalized futures rows."""
import csv
import datetime as dt
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

OUT = Path("public/data/nse-fo-latest.json")
BASE = "https://nsearchives.nseindia.com/content/fo"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/zip,application/octet-stream,*/*",
    "Referer": "https://www.nseindia.com/",
}
# UDiFF uses IDF for Index Futures and STF for Stock Futures.
# Keep legacy codes for compatibility with older NSE files.
FUTURES_INSTRUMENT_TYPES = {"IDF", "STF", "FUTIDX", "FUTSTK"}

def norm(value):
    return "".join(ch for ch in str(value).lower() if ch.isalnum())

def pick(row, *names):
    lookup = {norm(k): v for k, v in row.items()}
    for name in names:
        value = lookup.get(norm(name))
        if value is not None and str(value).strip() not in ("", "-"):
            return str(value).strip()
    return ""

def parse_date(value):
    value = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d%m%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ""

def fetch_for_date(day):
    stamp = day.strftime("%Y%m%d")
    filename = f"BhavCopy_NSE_FO_0_0_0_{stamp}_F_0000.csv.zip"
    url = f"{BASE}/{filename}"
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read()
    if not payload.startswith(b"PK"):
        raise ValueError(f"NSE returned a non-ZIP response for {stamp}")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV found inside NSE archive for {stamp}")
        with archive.open(csv_names[0]) as handle:
            text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text)
            rows = []
            instrument_counts = {}
            rejection_counts = {
                "missing_symbol": 0,
                "invalid_trade_date": 0,
                "invalid_expiry_date": 0,
                "missing_settlement": 0,
                "missing_underlying": 0,
                "missing_open_interest": 0,
            }
            sample_values = {}
            for raw in reader:
                instrument = pick(raw, "FinInstrmTp", "Instrument Type").upper()
                if instrument:
                    instrument_counts[instrument] = instrument_counts.get(instrument, 0) + 1
                if instrument not in FUTURES_INSTRUMENT_TYPES:
                    continue
                symbol = pick(raw, "TckrSymb", "Symbol")
                trade_date_raw = pick(raw, "BizDt", "Business Date")
                expiry_raw = pick(raw, "XpryDt", "Expiry Date")
                settle = pick(raw, "SttlmPric", "Settlement Price")
                underlying = pick(raw, "UndrlygPric", "Underlying Price")
                oi = pick(raw, "OpnIntrst", "Open Interest")
                trade_date = parse_date(trade_date_raw)
                expiry = parse_date(expiry_raw)
                missing = []
                for key, value in (
                    ("missing_symbol", symbol),
                    ("invalid_trade_date", trade_date),
                    ("invalid_expiry_date", expiry),
                    ("missing_settlement", settle),
                    ("missing_underlying", underlying),
                    ("missing_open_interest", oi),
                ):
                    if not value:
                        rejection_counts[key] += 1
                        missing.append(key)
                if missing:
                    if len(sample_values) < 3:
                        sample_values[str(len(sample_values) + 1)] = {
                            "headers": list(raw.keys()),
                            "instrumentType": instrument,
                            "values": {
                                "symbol": symbol,
                                "BizDt": trade_date_raw,
                                "XpryDt": expiry_raw,
                                "SttlmPric": settle,
                                "UndrlygPric": underlying,
                                "OpnIntrst": oi,
                            },
                            "missing": missing,
                        }
                    continue
                rows.append({
                    "symbol": symbol,
                    "tradeDate": trade_date,
                    "expiryDate": expiry,
                    "instrumentType": instrument,
                    "futuresClose": settle,
                    "spotClose": underlying,
                    "openInterest": oi,
                    "changeOpenInterest": pick(raw, "ChngInOpnIntrst", "Change in Open Interest"),
                    "previousFuturesClose": pick(raw, "Prvsclsgpric", "Previous Closing Price"),
                    "volume": pick(raw, "TtlTradgVol", "Total Traded Volume"),
                    "lotSize": pick(raw, "NewBrdLotQty", "Market Lot", "Lot Size"),
                })
    if not rows:
        diagnostics = {
            "csvHeaders": list(raw.keys()) if "raw" in locals() else [],
            "instrumentTypeCounts": instrument_counts,
            "requiredFieldRejections": rejection_counts,
            "sampleRejectedRows": sample_values,
        }
        raise ValueError(
            f"NSE archive {stamp} contained no valid index/stock futures rows; "
            f"diagnostics={json.dumps(diagnostics, separators=(',', ':'))}"
        )
    return filename, rows

def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    # NSE EOD archive can be delayed; retry the latest seven calendar dates.
    errors = []
    for offset in range(0, 8):
        day = today - dt.timedelta(days=offset)
        try:
            filename, rows = fetch_for_date(day)
            dates = sorted({row["tradeDate"] for row in rows})
            if len(dates) != 1:
                raise ValueError(f"Archive contains unexpected trade dates: {dates[:5]}")
            OUT.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "source": "NSE F&O UDiFF Common Bhavcopy Final",
                "sourceUrl": f"{BASE}/{filename}",
                "fileName": filename,
                "marketDate": dates[0],
                "retrievedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                "rowCount": len(rows),
                "rows": rows,
            }
            OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            print(f"Published {len(rows)} futures rows for {dates[0]} from {filename}")
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(f"{day.isoformat()}: {exc}")
            time.sleep(2)
    print("Unable to fetch a valid NSE F&O UDiFF bhavcopy:\n" + "\n".join(errors), file=sys.stderr)
    raise SystemExit(1)

if __name__ == "__main__":
    main()
