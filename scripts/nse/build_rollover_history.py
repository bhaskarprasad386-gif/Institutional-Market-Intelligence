#!/usr/bin/env python3
"""Build daily, contract-aware positional rollover metrics from NSE F&O history."""
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path("public/data/nse-fo-history")
OUTPUT = ROOT / "rollover-metrics.json"\nOUTCOMES_OUTPUT = ROOT / "rollover-outcomes.json"


def number(value, default=None):
    try:
        result = float(str(value).replace(",", "").strip())
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def direction(price_change_pct, oi_change):
    if price_change_pct is None or oi_change is None:
        return "INSUFFICIENT_DATA"
    if price_change_pct > 0 and oi_change > 0:
        return "LONG_BUILD_UP"
    if price_change_pct < 0 and oi_change > 0:
        return "SHORT_BUILD_UP"
    if price_change_pct > 0 and oi_change < 0:
        return "SHORT_COVERING"
    if price_change_pct < 0 and oi_change < 0:
        return "LONG_UNWINDING"
    return "MIXED"


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
            "oi": 0.0, "oi_change": 0.0, "oi_change_known": True,
            "weighted": 0.0, "weight": 0.0, "previous_weighted": 0.0,
            "previous_weight": 0.0, "lots": [], "volume": 0.0,
        }))
        for row in payload.get("rows", []):
            symbol = str(row.get("symbol", "")).strip()
            trade = str(row.get("tradeDate", "")).strip()
            expiry = str(row.get("expiryDate", "")).strip()
            if not symbol or trade != market_date or not expiry or expiry < trade:
                continue
            oi = number(row.get("openInterest"), -1)
            price = number(row.get("futuresClose"), 0)
            if oi is None or oi < 0 or price is None or price <= 0:
                continue
            bucket = grouped[symbol][expiry]
            bucket["oi"] += oi
            if oi > 0:
                bucket["weighted"] += price * oi
                bucket["weight"] += oi
                previous_close = number(row.get("previousFuturesClose"))
                if previous_close is not None and previous_close > 0:
                    bucket["previous_weighted"] += previous_close * oi
                    bucket["previous_weight"] += oi
            change = number(row.get("changeOpenInterest"))
            if change is None:
                bucket["oi_change_known"] = False
            else:
                bucket["oi_change"] += change
            lot = number(row.get("lotSize"), 0)
            if lot and lot > 0:
                bucket["lots"].append(lot)
            bucket["volume"] += number(row.get("volume"), 0) or 0

        for symbol, expiries in grouped.items():
            ordered = sorted(expiries.items())
            if len(ordered) < 2:
                continue
            selected = ordered[:3]
            near_expiry, near = selected[0]
            next_expiry, nxt = selected[1]
            far_expiry, far = selected[2] if len(selected) > 2 else (None, None)
            if near["oi"] + nxt["oi"] <= 0 or near["weight"] <= 0 or nxt["weight"] <= 0:
                continue

            def price_change(bucket):
                if not bucket or bucket["weight"] <= 0 or bucket["previous_weight"] <= 0:
                    return None
                current = bucket["weighted"] / bucket["weight"]
                previous = bucket["previous_weighted"] / bucket["previous_weight"]
                return (current / previous - 1) * 100 if previous > 0 else None

            def oi_change(bucket):
                return bucket["oi_change"] if bucket and bucket["oi_change_known"] else None

            near_price = near["weighted"] / near["weight"]
            next_price = nxt["weighted"] / nxt["weight"]
            points = next_price - near_price
            near_lots, next_lots = set(near["lots"]), set(nxt["lots"])
            lot_size = next(iter(near_lots)) if (
                len(near_lots) == 1 and len(next_lots) == 1 and near_lots == next_lots
            ) else None
            near_change, next_change, far_change = oi_change(near), oi_change(nxt), oi_change(far)
            total_oi = near["oi"] + nxt["oi"] + (far["oi"] if far else 0)
            total_change = None if near_change is None or next_change is None or (far and far_change is None) else (
                near_change + next_change + (far_change if far else 0)
            )
            next_far_oi = nxt["oi"] + (far["oi"] if far else 0)
            metrics.append({
                "symbol": symbol, "tradeDate": market_date,
                "nearExpiry": near_expiry, "nextExpiry": next_expiry,
                "farExpiry": far_expiry,
                "nearOi": near["oi"], "nextOi": nxt["oi"], "farOi": far["oi"] if far else 0,
                "totalOi": total_oi, "nextFarOi": next_far_oi,
                "rolloverPct": nxt["oi"] / (near["oi"] + nxt["oi"]) * 100,
                "extendedRolloverPct": next_far_oi / total_oi * 100 if total_oi > 0 else None,
                "farSharePct": far["oi"] / total_oi * 100 if far and total_oi > 0 else 0,
                "nearOiChange": near_change, "nextOiChange": next_change,
                "farOiChange": far_change, "totalOiChange": total_change,
                "nearPriceChangePct": price_change(near),
                "nextPriceChangePct": price_change(nxt),
                "nearBuildUp": direction(price_change(near), near_change),
                "nextBuildUp": direction(price_change(nxt), next_change),
                "nearVolume": near["volume"], "nextVolume": nxt["volume"],
                "nearFuturesClose": near_price, "nextFuturesClose": next_price,
                "spotClose": number(payload.get("rows", [{}])[0].get("spotClose")),
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
