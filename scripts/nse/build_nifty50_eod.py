#!/usr/bin/env python3
"""Build NIFTY 50 EOD technical and delivery dataset from NSE cash archives."""
import csv
import datetime as dt
import io
import json
import math
import urllib.request
from pathlib import Path

CONSTITUENTS_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "text/csv,*/*", "Referer": "https://www.niftyindices.com/"}
CASH_DIR = Path("public/data/nse-cash-delivery")
OUT = Path("public/data/nifty50-eod-latest.json")
CONSTITUENTS_CACHE = Path("public/data/nifty50-constituents.json")


def fetch_constituents():
    req = urllib.request.Request(CONSTITUENTS_URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(raw)))
        stocks = []
        for row in rows:
            symbol = (row.get("Symbol") or row.get("symbol") or "").strip().upper()
            name = (row.get("Company Name") or row.get("CompanyName") or row.get("company_name") or "").strip()
            sector = (row.get("Industry") or row.get("industry") or "").strip()
            if symbol:
                stocks.append({"symbol": symbol, "name": name or symbol, "sector": sector or None})
        if len(stocks) < 45:
            raise ValueError(f"Constituent file returned only {len(stocks)} symbols")
        CONSTITUENTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CONSTITUENTS_CACHE.write_text(json.dumps({"sourceUrl": CONSTITUENTS_URL, "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "count": len(stocks), "stocks": stocks}, separators=(",", ":")), encoding="utf-8")
        return stocks, "LIVE_NIFTY_INDICES_CONSTITUENTS"
    except Exception as exc:
        if CONSTITUENTS_CACHE.exists():
            cached = json.loads(CONSTITUENTS_CACHE.read_text(encoding="utf-8"))
            stocks = cached.get("stocks", [])
            if len(stocks) >= 45:
                return stocks, "CACHED_NIFTY_INDICES_CONSTITUENTS"
        raise RuntimeError(f"Unable to verify current NIFTY 50 constituents: {exc}") from exc


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains, losses = [], []
    for a, b in zip(values[:-1], values[1:]):
        delta = b - a
        gains.append(max(delta, 0.0)); losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def sma(values, period):
    return round(sum(values[-period:]) / period, 2) if len(values) >= period else None


def weekly_rows(rows):
    by_week = {}
    for row in rows:
        day = dt.date.fromisoformat(row["tradeDate"])
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        if key not in by_week or row["tradeDate"] > by_week[key]["tradeDate"]:
            by_week[key] = row
    return [by_week[key] for key in sorted(by_week)]


def load_history():
    by_symbol = {}
    source_dates = set()
    for path in sorted(CASH_DIR.glob("????-??-??.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        day = payload.get("marketDate")
        if not day:
            continue
        source_dates.add(day)
        for row in payload.get("rows", []):
            if row.get("series") != "EQ" or not row.get("symbol") or row.get("closePrice") is None:
                continue
            by_symbol.setdefault(row["symbol"].upper(), []).append(row)
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda x: x["tradeDate"])
    return by_symbol, source_dates


def main():
    stocks, constituent_status = fetch_constituents()
    history, dates = load_history()
    latest_date = max(dates) if dates else None
    output = []
    for stock in stocks:
        symbol = stock["symbol"]
        rows = history.get(symbol, [])
        latest = rows[-1] if rows else None
        closes = [float(row["closePrice"]) for row in rows]
        weeks = weekly_rows(rows)
        weekly_closes = [float(row["closePrice"]) for row in weeks]
        output.append({
            **stock,
            "marketDate": latest.get("tradeDate") if latest else None,
            "open": latest.get("openPrice"), "high": latest.get("highPrice"), "low": latest.get("lowPrice"),
            "close": latest.get("closePrice"), "previousClose": latest.get("previousClose"),
            "lastPrice": latest.get("closePrice"), "vwap": latest.get("vwap"),
            "volume": latest.get("tradedQuantity"), "deliveryQuantity": latest.get("deliveryQuantity"),
            "deliveryPct": latest.get("deliveryPct"), "tradeCount": latest.get("tradeCount"),
            "previousClose": rows[-2].get("closePrice") if len(rows) >= 2 else None,\n            "dailyChangePct": round((float(latest["closePrice"]) / float(rows[-2]["closePrice"]) - 1) * 100, 2) if len(rows) >= 2 and float(rows[-2]["closePrice"]) > 0 else None,
            "sma20Daily": sma(closes, 20), "sma50Daily": sma(closes, 50),
            "sma20Weekly": sma(weekly_closes, 20), "sma50Weekly": sma(weekly_closes, 50),
            "rsiDaily14": rsi(closes, 14), "rsiWeekly14": rsi(weekly_closes, 14),
            "dailyHistorySessions": len(rows), "weeklyHistorySessions": len(weeks),
            "deliveryStatus": "AVAILABLE" if latest and latest.get("deliveryQuantity") is not None and latest.get("deliveryPct") is not None else "PARTIAL",
            "technicalStatus": "READY" if latest else "WAITING_FOR_NSE_CASH_HISTORY",
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schemaVersion": 1, "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "marketDate": latest_date, "source": "NSE Full Bhavcopy and Security Deliverable Data",
        "sourceUrl": "https://www.nseindia.com/all-reports",
        "constituentSource": CONSTITUENTS_URL, "constituentStatus": constituent_status,
        "constituentCount": len(stocks), "sessionsAvailable": len(dates),
        "historyPolicy": "Only archived NSE EQ observations are used. Missing indicators remain null until sufficient history exists.",
        "rows": output
    }, separators=(",", ":")), encoding="utf-8")
    ready = sum(1 for row in output if row["close"] is not None)
    print(f"NIFTY 50 EOD built: marketDate={latest_date}, constituents={len(stocks)}, price rows={ready}, cash sessions={len(dates)}")


if __name__ == "__main__":
    main()
