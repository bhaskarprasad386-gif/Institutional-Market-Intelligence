#!/usr/bin/env python3
"""Build daily, contract-aware positional rollover metrics from NSE F&O history."""
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path("public/data/nse-fo-history")
OUTPUT = ROOT / "rollover-metrics.json"
OUTCOMES_OUTPUT = ROOT / "rollover-outcomes.json"


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
        spot_by_symbol = defaultdict(list)
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
            spot = number(row.get("spotClose"))
            if spot is not None and spot > 0:
                spot_by_symbol[symbol].append(spot)
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
                "spotClose": sorted(spot_by_symbol[symbol])[len(spot_by_symbol[symbol]) // 2] if spot_by_symbol[symbol] else None,
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

    # Research-only forward outcomes; never used as same-day signal inputs.
    sessions = sorted({x["marketDate"] for x in dates})
    symbol_sessions = defaultdict(list)
    spot_lookup = {}
    for metric in metrics:
        spot = number(metric.get("spotClose"))
        if spot is not None and spot > 0:
            symbol_sessions[metric["symbol"]].append(metric["tradeDate"])
            spot_lookup[(metric["symbol"], metric["tradeDate"])] = spot
    for symbol in symbol_sessions:
        symbol_sessions[symbol] = sorted(set(symbol_sessions[symbol]))

    outcomes = []
    threshold_pct = 0.5
    for row in metrics:
        start_price = number(row.get("spotClose"))
        own_sessions = symbol_sessions.get(row["symbol"], [])
        idx = own_sessions.index(row["tradeDate"]) if row["tradeDate"] in own_sessions else None
        if start_price is None or start_price <= 0 or idx is None:
            continue
        item = {"symbol": row["symbol"], "signalDate": row["tradeDate"],
                "nearExpiry": row["nearExpiry"], "nextExpiry": row["nextExpiry"],
                "nextBuildUp": row.get("nextBuildUp"), "spotAtSignal": start_price}
        for horizon in (5, 10, 20):
            future_day = own_sessions[idx + horizon] if idx + horizon < len(own_sessions) else None
            future_price = number(spot_lookup.get((row["symbol"], future_day))) if future_day else None
            ret = (future_price / start_price - 1) * 100 if future_price is not None and future_price > 0 else None
            item[f"return{horizon}dPct"] = ret
            item[f"outcome{horizon}d"] = ("UP" if ret is not None and ret >= threshold_pct else
                "DOWN" if ret is not None and ret <= -threshold_pct else
                "FLAT" if ret is not None else "PENDING")
            item[f"correct{horizon}d"] = (
                (item["nextBuildUp"] == "LONG_BUILD_UP" and ret >= threshold_pct)
                or (item["nextBuildUp"] == "SHORT_BUILD_UP" and ret <= -threshold_pct)
            ) if ret is not None and abs(ret) >= threshold_pct and item["nextBuildUp"] in ("LONG_BUILD_UP", "SHORT_BUILD_UP") else None
        outcomes.append(item)

    # One first directional observation per symbol and expiry pair.
    cycle_seen = set()
    cycle_outcomes = []
    for item in outcomes:
        signal = item.get("nextBuildUp")
        if signal not in ("LONG_BUILD_UP", "SHORT_BUILD_UP"):
            continue
        cycle_key = (item["symbol"], item["nearExpiry"], item["nextExpiry"])
        if cycle_key in cycle_seen:
            continue
        cycle_seen.add(cycle_key)
        item["cycleKey"] = "|".join(cycle_key)
        cycle_outcomes.append(item)

    # Chronological 70/30 split, with a 20-session purge before holdout.
    unique_signal_dates = sorted({x["signalDate"] for x in cycle_outcomes})
    split_index = min(len(unique_signal_dates), max(1, int(len(unique_signal_dates) * 0.7)))
    holdout_start = unique_signal_dates[split_index] if split_index < len(unique_signal_dates) else None
    holdout_index = sessions.index(holdout_start) if holdout_start in sessions else None
    development_cutoff = sessions[max(0, holdout_index - 20)] if holdout_index is not None and holdout_index >= 20 else holdout_start
    development = [x for x in cycle_outcomes if development_cutoff is not None and x["signalDate"] < development_cutoff]
    holdout = [x for x in cycle_outcomes if holdout_start is not None and x["signalDate"] >= holdout_start]

    def summarize(rows):
        summary = {}
        for horizon in (5, 10, 20):
            for signal in ("LONG_BUILD_UP", "SHORT_BUILD_UP"):
                eligible = [x for x in rows if x["nextBuildUp"] == signal]
                sample = [x for x in eligible if x.get(f"correct{horizon}d") is not None]
                hits = sum(bool(x[f"correct{horizon}d"]) for x in sample)
                cost_scenarios = {}
                for cost_bps in (10, 20, 30):
                    cost_pct = cost_bps / 100
                    if signal == "LONG_BUILD_UP":
                        net_hits = sum(1 for x in sample if x[f"return{horizon}dPct"] - cost_pct >= threshold_pct)
                    else:
                        net_hits = sum(1 for x in sample if x[f"return{horizon}dPct"] + cost_pct <= -threshold_pct)
                    cost_scenarios[str(cost_bps)] = {
                        "assumedRoundTripCostBps": cost_bps,
                        "netDirectionalHits": net_hits,
                        "netPrecisionPct": round(net_hits / len(sample) * 100, 2) if sample else None,
                    }
                summary[f"{signal}_{horizon}D"] = {
                    "signals": len(eligible),
                    "evaluatedSignals": len(sample), "correctSignals": hits,
                    "precisionPct": round(hits / len(sample) * 100, 2) if sample else None,
                    "flatExcluded": sum(x.get(f"outcome{horizon}d") == "FLAT" for x in eligible),
                    "pending": sum(x.get(f"outcome{horizon}d") == "PENDING" for x in eligible),
                    "costSensitivity": cost_scenarios,
                }
        return summary

    OUTCOMES_OUTPUT.write_text(json.dumps({
        "source": "Point-in-time signals matched to symbol-specific future NSE spot closes",
        "thresholdPct": threshold_pct, "horizonsTradingSessions": [5, 10, 20],
        "sessions": len(sessions), "rawOutcomeCount": len(outcomes),
        "cycleSignalCount": len(cycle_outcomes),
        "holdoutStartDate": holdout_start, "developmentCutoffExclusive": development_cutoff,
        "developmentPurgeSessions": 20,
        "costSensitivityAssumptions": "Hypothetical round-trip cost scenarios of 10/20/30 bps; not actual broker charges.",
        "stats": summarize(cycle_outcomes),
        "developmentStats": summarize(development),
        "holdoutStats": summarize(holdout),
        "outcomes": outcomes, "cycleOutcomes": cycle_outcomes,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"Built {OUTPUT}: {len(dates)} sessions, {len(metrics)} symbol/day rollover metrics")
    print(f"Built {OUTCOMES_OUTPUT}: {len(outcomes)} forward outcome rows")
    return result


if __name__ == "__main__":
    build()
