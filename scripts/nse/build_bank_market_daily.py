#!/usr/bin/env python3
"""Build daily bank technical and delivery snapshot from official NSE cash archives."""
import datetime as dt
import json
from pathlib import Path

BANKS = [
    ("HDFCBANK","HDFC Bank"),("ICICIBANK","ICICI Bank"),("SBIN","State Bank of India"),
    ("KOTAKBANK","Kotak Mahindra Bank"),("AXISBANK","Axis Bank"),("PNB","Punjab National Bank"),
    ("UNIONBANK","Union Bank of India"),("BANKBARODA","Bank of Baroda"),("CANBK","Canara Bank"),
    ("FEDERALBNK","Federal Bank"),
]
DATA = Path("public/data/nse-cash-delivery")
OUT = Path("public/data/bank-market-daily.json")

def sma(values, period):
    return round(sum(values[-period:]) / period, 2) if len(values) >= period else None

def weekly_closes(rows):
    # Last available NSE session close in each ISO week.
    latest_by_week = {}
    for row in rows:
        day = dt.date.fromisoformat(row["tradeDate"])
        iso = day.isocalendar()
        latest_by_week[(iso.year, iso.week)] = float(row["closePrice"])
    return [latest_by_week[key] for key in sorted(latest_by_week)]

def main():
    files = sorted(DATA.glob("????-??-??.json"))
    by_symbol = {symbol: [] for symbol, _ in BANKS}
    source_dates = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        day = payload.get("marketDate")
        if not day:
            continue
        source_dates.append(day)
        for row in payload.get("rows", []):
            symbol = row.get("symbol")
            if symbol in by_symbol and row.get("series") == "EQ" and row.get("closePrice") is not None:
                by_symbol[symbol].append(row)
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda x: x["tradeDate"])
    latest_date = max(source_dates) if source_dates else None
    output = []
    for symbol, name in BANKS:
        rows = by_symbol[symbol]
        latest = rows[-1] if rows else None
        closes = [float(x["closePrice"]) for x in rows]
        delivery = [x for x in rows if x.get("deliveryPct") is not None]
        last_delivery = delivery[-1] if delivery else None
        output.append({
            "symbol": symbol, "name": name,
            "marketDate": latest.get("tradeDate") if latest else None,
            "close": latest.get("closePrice") if latest else None,
            "sma20Daily": sma(closes, 20), "sma50Daily": sma(closes, 50),
            "sma20Weekly": sma(weekly_closes(rows), 20), "sma50Weekly": sma(weekly_closes(rows), 50),
            "deliveryPct": last_delivery.get("deliveryPct") if last_delivery else None,
            "deliveryPctDate": last_delivery.get("tradeDate") if last_delivery else None,
            "deliveryPctPrevious": delivery[-2].get("deliveryPct") if len(delivery) >= 2 else None,
            "deliveryPct5SessionAvg": round(sum(float(x["deliveryPct"]) for x in delivery[-5:])/5,2) if len(delivery)>=5 else None,
            "deliveryPct20SessionAvg": round(sum(float(x["deliveryPct"]) for x in delivery[-20:])/20,2) if len(delivery)>=20 else None,
            "historySessions": len(rows),
            "status": "READY" if latest else "WAITING_FOR_NSE_CASH_HISTORY",
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source":"NSE Full Bhavcopy and Security Deliverable Data",
        "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "marketDate":latest_date,"sessionsAvailable":len(set(source_dates)),"rows":output
    },separators=(",",":")),encoding="utf-8")
    print(f"Built bank daily snapshot: marketDate={latest_date}, sessions={len(set(source_dates))}, banks={len(output)}")

if __name__ == "__main__":
    main()
