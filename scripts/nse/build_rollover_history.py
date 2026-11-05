#!/usr/bin/env python3
"""Build compact daily rollover metrics from every archived NSE F&O session."""
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path("public/data/nse-fo-history")
OUTPUT = ROOT / "rollover-metrics.json"


def number(value, default=0.0):
    try:
        result = float(str(value).replace(",", "").strip())
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def build():
    index_path = ROOT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    dates = index.get("dates", [])
    metrics = []
    for item in dates:
        market_date = item["marketDate"]
        payload = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
        if payload.get("marketDate") != market_date:
            raise ValueError(f"Archive date mismatch: {item['path']}")
        grouped = defaultdict(lambda: defaultdict(lambda: {
            "oi": 0.0, "weighted": 0.0, "weight": 0.0, "lots": []
        }))
        for row in payload.get("rows", []):
            symbol = str(row.get("symbol", "")).strip()
            trade = str(row.get("tradeDate", "")).strip()
            expiry = str(row.get("expiryDate", "")).strip()
            if not symbol or trade != market_date or not expiry or expiry < trade:
                continue
            oi = number(row.get("openInterest"), -1)
            price = number(row.get("futuresClose"), 0)
            if oi < 0 or price <= 0:
                continue
            bucket = grouped[symbol][expiry]
            bucket["oi"] += oi
            if oi > 0:
                bucket["weighted"] += price * oi
                bucket["weight"] += oi
            lot = number(row.get("lotSize"), 0)
            if lot > 0:
                bucket["lots"].append(lot)
        for symbol, expiries in grouped.items():
            ordered = sorted(expiries.items())
            if len(ordered) < 2:
                continue
            near_expiry, near = ordered[0]
            next_expiry, nxt = ordered[1]
            if near["oi"] + nxt["oi"] <= 0 or near["weight"] <= 0 or nxt["weight"] <= 0:
                continue
            near_price = near["weighted"] / near["weight"]
            next_price = nxt["weighted"] / nxt["weight"]
            if near_price <= 0:
                continue
            points = next_price - near_price
            near_lot = near["lots"][0] if near["lots"] else None
            next_lot = nxt["lots"][0] if nxt["lots"] else None
            lot_size = near_lot if near_lot and near_lot == next_lot else None
            metrics.append({
                "symbol": symbol, "tradeDate": market_date,
                "nearExpiry": near_expiry, "nextExpiry": next_expiry,
                "nearOi": near["oi"], "nextOi": nxt["oi"],
                "rolloverPct": nxt["oi"] / (near["oi"] + nxt["oi"]) * 100,
                "nearFuturesClose": near_price, "nextFuturesClose": next_price,
                "rolloverCostPoints": points, "rolloverCostPct": points / near_price * 100,
                **({"lotSize": lot_size, "rolloverCostPerLot": points * lot_size} if lot_size else {}),
                "rolloverPctFlag": "INSUFFICIENT_PEERS",
                "rolloverCostFlag": "INSUFFICIENT_PEERS", "peerCount": 0,
            })
    metrics.sort(key=lambda row: (row["tradeDate"], row["symbol"]))
    result = {
        "source": "Derived from complete NSE F&O dated history archive",
        "updatedAt": index.get("updatedAt"),
        "archivedSessions": len(dates),
        "oldestMarketDate": min((x["marketDate"] for x in dates), default=None),
        "newestMarketDate": max((x["marketDate"] for x in dates), default=None),
        "metricCount": len(metrics),
        "metrics": metrics,
    }
    OUTPUT.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"Built {OUTPUT}: {len(dates)} sessions, {len(metrics)} symbol/day rollover metrics")
    return result


if __name__ == "__main__":
    build()
