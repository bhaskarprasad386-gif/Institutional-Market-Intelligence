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



def calculate_prior_volatility(symbol_spot_series, symbol, signal_date):
    """Annualized volatility from up to 20 prior symbol sessions; excludes signal day."""
    history = [(day, price) for day, price in symbol_spot_series.get(symbol, []) if day < signal_date]
    if len(history) < 11:
        return None, "INSUFFICIENT_HISTORY"
    history = history[-21:]
    returns = [
        history[i][1] / history[i - 1][1] - 1
        for i in range(1, len(history))
        if history[i - 1][1] > 0
    ]
    if len(returns) < 10:
        return None, "INSUFFICIENT_HISTORY"
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    annualized = math.sqrt(variance) * math.sqrt(252) * 100
    regime = "LOW" if annualized < 20 else "MEDIUM" if annualized < 40 else "HIGH"
    return annualized, regime


def calculate_prior_spot_momentum(symbol_spot_series, symbol, signal_date, horizon=5):
    """Signal-close return versus the close N symbol sessions earlier; no future data."""
    history = [(day, price) for day, price in symbol_spot_series.get(symbol, []) if day <= signal_date]
    if len(history) <= horizon:
        return None
    prior_price = history[-(horizon + 1)][1]
    current_price = history[-1][1]
    if prior_price is None or current_price is None or prior_price <= 0 or current_price <= 0:
        return None
    return (current_price / prior_price - 1) * 100


def add_point_in_time_market_momentum(metrics, market_spot_by_date, horizon=5):
    """Attach NIFTY trend using only the signal date and its prior archived index sessions."""
    series = sorted(
        (day, price) for day, price in market_spot_by_date.items()
        if price is not None and price > 0
    )
    by_date = {day: index for index, (day, _) in enumerate(series)}
    for row in metrics:
        index = by_date.get(row["tradeDate"])
        momentum = None
        if index is not None and index >= horizon:
            prior = series[index - horizon][1]
            current = series[index][1]
            if prior > 0:
                momentum = (current / prior - 1) * 100
        row["niftyMomentum5dPct"] = momentum
        # A 0.25% dead band avoids labelling negligible index moves as trend.
        row["niftyTrend5d"] = (
            "INSUFFICIENT_HISTORY" if momentum is None else
            "UP" if momentum > 0.25 else "DOWN" if momentum < -0.25 else "FLAT"
        )
    return metrics


def purge_development_signals(cycle_outcomes, symbol_sessions, holdout_start):
    """Keep development labels only when their 20-session endpoint precedes holdout."""
    # With fewer than two distinct signal dates there is no holdout partition.
    # Keep the observations in development and report the holdout as unavailable.
    if holdout_start is None:
        return list(cycle_outcomes), 0

    development = []
    purged = 0
    for item in cycle_outcomes:
        if item["signalDate"] >= holdout_start:
            continue
        own_sessions = symbol_sessions.get(item["symbol"], [])
        signal_idx = own_sessions.index(item["signalDate"]) if item["signalDate"] in own_sessions else None
        symbol_holdout_idx = next((i for i, day in enumerate(own_sessions) if day >= holdout_start), None)
        if signal_idx is not None and symbol_holdout_idx is not None and signal_idx + 20 < symbol_holdout_idx:
            development.append(item)
        else:
            purged += 1
    return development, purged


def build_walk_forward_folds(cycle_outcomes, symbol_sessions, minimum_train_fraction=0.6, fold_count=4, minimum_test_dates=5):
    """Create non-overlapping chronological test folds with per-symbol 20-session purge."""
    dates = sorted({item["signalDate"] for item in cycle_outcomes})
    if not dates or fold_count < 1 or not 0 < minimum_train_fraction < 1:
        return []
    first_test_idx = max(1, int(len(dates) * minimum_train_fraction))
    remaining = dates[first_test_idx:]
    if len(remaining) < minimum_test_dates:
        return []
    block_size = max(minimum_test_dates, math.ceil(len(remaining) / fold_count))
    folds = []
    for offset in range(0, len(remaining), block_size):
        test_dates = remaining[offset:offset + block_size]
        if len(test_dates) < minimum_test_dates:
            continue
        test_start, test_end = test_dates[0], test_dates[-1]
        development, purged = purge_development_signals(cycle_outcomes, symbol_sessions, test_start)
        test_rows = [item for item in cycle_outcomes if test_start <= item["signalDate"] <= test_end]
        folds.append({
            "fold": len(folds) + 1,
            "testStartDate": test_start,
            "testEndDate": test_end,
            "testSignalDates": len(test_dates),
            "developmentSignalsAfterPurge": len(development),
            "purgedDevelopmentSignals": purged,
            "testRows": test_rows,
        })
    return folds

def apply_daily_rollover_flags(metrics):
    """Match the live scanner's same-day cross-sectional 75th-percentile flags."""
    by_date = defaultdict(list)
    for row in metrics:
        by_date[row["tradeDate"]].append(row)
    flagged = []
    for rows in by_date.values():
        enough_peers = len(rows) >= 5
        rollover_values = [row["rolloverPct"] for row in rows]
        positive_costs = [row["rolloverCostPct"] for row in rows if row["rolloverCostPct"] > 0]
        pct_cutoff = sorted(rollover_values)[math.ceil(0.75 * len(rollover_values)) - 1] if enough_peers else None
        cost_cutoff = sorted(positive_costs)[math.ceil(0.75 * len(positive_costs)) - 1] if len(positive_costs) >= 5 else None
        for row in rows:
            pct_flag = "INSUFFICIENT_PEERS" if not enough_peers else (
                "HIGH" if row["rolloverPct"] >= pct_cutoff else "NORMAL"
            )
            cost_flag = "ROLL_CREDIT" if row["rolloverCostPct"] < 0 else (
                "INSUFFICIENT_PEERS" if not enough_peers or cost_cutoff is None else
                "HIGH" if row["rolloverCostPct"] >= cost_cutoff else "NORMAL"
            )
            flagged.append({**row, "rolloverPctFlag": pct_flag,
                            "rolloverCostFlag": cost_flag, "peerCount": len(rows)})
    return sorted(flagged, key=lambda row: (row["tradeDate"], row["symbol"]))


def add_point_in_time_rollover_momentum(metrics):
    """Attach 3/5-session rollover-share and total-OI momentum without lookahead."""
    by_symbol = defaultdict(list)
    for row in metrics:
        by_symbol[row["symbol"]].append(row)
    for rows in by_symbol.values():
        rows.sort(key=lambda row: row["tradeDate"])
        for index, row in enumerate(rows):
            for horizon in (3, 5):
                prior_index = index - horizon
                share_key = f"nextShareMomentum{horizon}d"
                oi_key = f"totalOiMomentum{horizon}dPct"
                cost_key = f"rolloverCostMomentum{horizon}dPct"
                if prior_index < 0:
                    row[share_key] = None
                    row[oi_key] = None
                    row[cost_key] = None
                    continue
                prior = rows[prior_index]
                current_denominator = row["nearOi"] + row["nextOi"]
                prior_denominator = prior["nearOi"] + prior["nextOi"]
                row[share_key] = (row["nextOi"] / current_denominator * 100 - prior["nextOi"] / prior_denominator * 100) if current_denominator > 0 and prior_denominator > 0 else None
                prior_oi = number(prior.get("totalOi"))
                current_oi = number(row.get("totalOi"))
                row[oi_key] = (current_oi / prior_oi - 1) * 100 if prior_oi is not None and current_oi is not None and prior_oi > 0 else None
                prior_cost = number(prior.get("rolloverCostPct"))
                current_cost = number(row.get("rolloverCostPct"))
                # Difference in rollover-cost percentage points; positive means
                # the next-expiry premium/cost is widening versus the near expiry.
                row[cost_key] = current_cost - prior_cost if current_cost is not None and prior_cost is not None else None
    return metrics


def build():
    index_path = ROOT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    dates = index.get("dates", [])
    metrics = []
    nifty_spot_by_date = {}
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

        nifty_prices = spot_by_symbol.get("NIFTY", [])
        if nifty_prices:
            ordered_nifty_prices = sorted(nifty_prices)
            nifty_spot_by_date[market_date] = ordered_nifty_prices[len(ordered_nifty_prices) // 2]

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

    metrics = apply_daily_rollover_flags(metrics)
    metrics = add_point_in_time_rollover_momentum(metrics)
    metrics = add_point_in_time_market_momentum(metrics, nifty_spot_by_date, horizon=5)
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
    symbol_spot_series = {
        symbol: [(day, spot_lookup[(symbol, day)]) for day in days]
        for symbol, days in symbol_sessions.items()
    }

    def prior_volatility(symbol, signal_date):
        return calculate_prior_volatility(symbol_spot_series, symbol, signal_date)
    for row in metrics:
        start_price = number(row.get("spotClose"))
        own_sessions = symbol_sessions.get(row["symbol"], [])
        idx = own_sessions.index(row["tradeDate"]) if row["tradeDate"] in own_sessions else None
        if start_price is None or start_price <= 0 or idx is None:
            continue
        vol20, vol_regime = prior_volatility(row["symbol"], row["tradeDate"])
        item = {"symbol": row["symbol"], "signalDate": row["tradeDate"],
                "nearExpiry": row["nearExpiry"], "nextExpiry": row["nextExpiry"],
                "nextBuildUp": row.get("nextBuildUp"), "spotAtSignal": start_price,
                "rolloverPct": row["rolloverPct"], "rolloverCostPct": row["rolloverCostPct"],
                "rolloverPctFlag": row["rolloverPctFlag"], "rolloverCostFlag": row["rolloverCostFlag"],
                "peerCount": row["peerCount"],
                "nextShareMomentum3d": row.get("nextShareMomentum3d"),
                "nextShareMomentum5d": row.get("nextShareMomentum5d"),
                "totalOiMomentum3dPct": row.get("totalOiMomentum3dPct"),
                "totalOiMomentum5dPct": row.get("totalOiMomentum5dPct"),
                "rolloverCostMomentum3dPct": row.get("rolloverCostMomentum3dPct"),
                "rolloverCostMomentum5dPct": row.get("rolloverCostMomentum5dPct"),
                "niftyMomentum5dPct": row.get("niftyMomentum5dPct"),
                "niftyTrend5d": row.get("niftyTrend5d", "INSUFFICIENT_HISTORY"),
                "realizedVol20dAnnualizedPct": vol20, "volatilityRegime": vol_regime,
                "spotMomentum5dPct": calculate_prior_spot_momentum(
                    symbol_spot_series, row["symbol"], row["tradeDate"], 5)}
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
    # Purging uses each symbol's own observation calendar, not a global cutoff date.
    holdout = [x for x in cycle_outcomes if holdout_start is not None and x["signalDate"] >= holdout_start]
    # Purge by each symbol's own observation calendar, not the market-wide calendar.
    development, purged_development_signals = purge_development_signals(
        cycle_outcomes, symbol_sessions, holdout_start
    )

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
        regime_summary = {}
        for regime in ("LOW", "MEDIUM", "HIGH", "INSUFFICIENT_HISTORY"):
            regime_rows = [x for x in rows if x.get("volatilityRegime") == regime]
            regime_summary[regime] = {}
            for horizon in (5, 10, 20):
                for signal in ("LONG_BUILD_UP", "SHORT_BUILD_UP"):
                    eligible = [x for x in regime_rows if x["nextBuildUp"] == signal]
                    sample = [x for x in eligible if x.get(f"correct{horizon}d") is not None]
                    hits = sum(bool(x[f"correct{horizon}d"]) for x in sample)
                    regime_summary[regime][f"{signal}_{horizon}D"] = {
                        "signals": len(eligible), "evaluatedSignals": len(sample),
                        "correctSignals": hits,
                        "precisionPct": round(hits / len(sample) * 100, 2) if sample else None,
                    }
        return {"overall": summary, "byVolatilityRegime": regime_summary}

    walk_forward_folds = build_walk_forward_folds(cycle_outcomes, symbol_sessions)
    walk_forward_rows = [item for fold in walk_forward_folds for item in fold["testRows"]]
    walk_forward_summary = summarize(walk_forward_rows)["overall"]

    def cohort_breadth(selected):
        """Measure symbol/date diversity and largest single-contributor concentration."""
        symbol_counts = defaultdict(int)
        date_counts = defaultdict(int)
        for item in selected:
            symbol_counts[item["symbol"]] += 1
            date_counts[item["signalDate"]] += 1
        total = len(selected)
        max_symbol = max(symbol_counts.values(), default=0)
        max_date = max(date_counts.values(), default=0)
        return {
            "uniqueSymbols": len(symbol_counts),
            "uniqueSignalDates": len(date_counts),
            "maxSymbolSignals": max_symbol,
            "maxSymbolSharePct": round(max_symbol / total * 100, 2) if total else None,
            "maxDateSignals": max_date,
            "maxDateSharePct": round(max_date / total * 100, 2) if total else None,
        }

    def rollover_condition_summary(rows):
        cohorts = {
            "ALL_DIRECTIONAL": rows,
            "HIGH_ROLLOVER_PCT": [x for x in rows if x.get("rolloverPctFlag") == "HIGH"],
            "HIGH_ROLLOVER_COST": [x for x in rows if x.get("rolloverCostFlag") == "HIGH"],
            "HIGH_BOTH": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH"],
            "HIGH_BOTH_MOMENTUM_UP": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and (x.get("nextShareMomentum5d") or 0) > 0 and (x.get("totalOiMomentum5dPct") or 0) > 0],
            "HIGH_BOTH_MOMENTUM_DOWN": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and (x.get("nextShareMomentum5d") or 0) < 0 and (x.get("totalOiMomentum5dPct") or 0) > 0],
            "HIGH_BOTH_SHARE_UP_OI_DOWN": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x.get("totalOiMomentum5dPct") is not None and x["nextShareMomentum5d"] > 0 and x["totalOiMomentum5dPct"] < 0],
            "HIGH_BOTH_SHARE_DOWN_OI_DOWN": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x.get("totalOiMomentum5dPct") is not None and x["nextShareMomentum5d"] < 0 and x["totalOiMomentum5dPct"] < 0],
            "HIGH_BOTH_COST_RISING": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0],
            "HIGH_BOTH_COST_FALLING": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] < 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_NIFTY_DOWN": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("niftyTrend5d") == "DOWN"],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_NIFTY_UP": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("niftyTrend5d") == "UP"],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_NIFTY_FLAT": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("niftyTrend5d") == "FLAT"],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_NIFTY_INSUFFICIENT": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("niftyTrend5d") == "INSUFFICIENT_HISTORY"],
            "HIGH_BOTH_SHARE_DOWN_COST_FALLING": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] < 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_PRICE_DOWN": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("spotMomentum5dPct") is not None and x["spotMomentum5dPct"] < 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_PRICE_UP": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("spotMomentum5dPct") is not None and x["spotMomentum5dPct"] > 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_PRICE_DOWN_OI_UP": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("spotMomentum5dPct") is not None and x["spotMomentum5dPct"] < 0 and x.get("totalOiMomentum5dPct") is not None and x["totalOiMomentum5dPct"] > 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_PRICE_DOWN_OI_DOWN": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("spotMomentum5dPct") is not None and x["spotMomentum5dPct"] < 0 and x.get("totalOiMomentum5dPct") is not None and x["totalOiMomentum5dPct"] < 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_PRICE_UP_OI_UP": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("spotMomentum5dPct") is not None and x["spotMomentum5dPct"] > 0 and x.get("totalOiMomentum5dPct") is not None and x["totalOiMomentum5dPct"] > 0],
            "HIGH_BOTH_SHARE_DOWN_COST_RISING_PRICE_UP_OI_DOWN": [x for x in rows if x.get("rolloverPctFlag") == "HIGH" and x.get("rolloverCostFlag") == "HIGH" and x.get("nextShareMomentum5d") is not None and x["nextShareMomentum5d"] < 0 and x.get("rolloverCostMomentum5dPct") is not None and x["rolloverCostMomentum5dPct"] > 0 and x.get("spotMomentum5dPct") is not None and x["spotMomentum5dPct"] > 0 and x.get("totalOiMomentum5dPct") is not None and x["totalOiMomentum5dPct"] < 0],
            **{
                f"HIGH_BOTH_SHARE_DOWN_COST_RISING_{trend}_PRICE_{price}_OI_{oi}": [
                    x for x in rows
                    if x.get("rolloverPctFlag") == "HIGH"
                    and x.get("rolloverCostFlag") == "HIGH"
                    and x.get("nextShareMomentum5d") is not None
                    and x["nextShareMomentum5d"] < 0
                    and x.get("rolloverCostMomentum5dPct") is not None
                    and x["rolloverCostMomentum5dPct"] > 0
                    and x.get("niftyTrend5d") == trend
                    and x.get("spotMomentum5dPct") is not None
                    and (x["spotMomentum5dPct"] < 0 if price == "DOWN" else x["spotMomentum5dPct"] > 0)
                    and x.get("totalOiMomentum5dPct") is not None
                    and (x["totalOiMomentum5dPct"] > 0 if oi == "UP" else x["totalOiMomentum5dPct"] < 0)
                ]
                for trend in ("DOWN", "UP", "FLAT")
                for price, oi in (("DOWN", "UP"), ("DOWN", "DOWN"), ("UP", "UP"), ("UP", "DOWN"))
            },
        }
        return {
            name: {
                "signalCount": len(selected),
                "breadth": cohort_breadth(selected),
                "stats": summarize(selected)["overall"],
                # Regime labels use only prior symbol-session spot returns.
                # Keep the same cohort definitions across holdout and each fold.
                "byVolatilityRegime": summarize(selected)["byVolatilityRegime"],
            }
            for name, selected in cohorts.items()
        }

    rollover_condition_stats = {
        "flagMethod": "Same-day cross-sectional 75th percentile, matching live scanner; at least 5 total peers and 5 positive-cost peers. No future observations are used.",
        "momentumMethod": "Point-in-time 3/5 symbol-session change in next-expiry OI share (percentage points), total near+next+far OI (percent), and rollover cost (percentage points); current day compared only with prior archived symbol sessions.",
        "marketTrendMethod": "NIFTY spot-close return over the signal date and five prior archived NIFTY sessions; UP above +0.25%, DOWN below -0.25%, otherwise FLAT. Missing index history is kept separate. No future index observations are used.",
        "development": rollover_condition_summary(development),
        "holdout": rollover_condition_summary(holdout),
        "walkForward": rollover_condition_summary(walk_forward_rows),
        "walkForwardFolds": [
            {"fold": fold["fold"], "testStartDate": fold["testStartDate"],
             "testEndDate": fold["testEndDate"],
             "cohorts": rollover_condition_summary(fold["testRows"])}
            for fold in walk_forward_folds
        ],
    }
    walk_forward_fold_summaries = [
        {key: value for key, value in fold.items() if key != "testRows"}
        | {"stats": summarize(fold["testRows"])["overall"]}
        for fold in walk_forward_folds
    ]

    OUTCOMES_OUTPUT.write_text(json.dumps({
        "source": "Point-in-time signals matched to symbol-specific future NSE spot closes",
        "thresholdPct": threshold_pct, "horizonsTradingSessions": [5, 10, 20],
        "sessions": len(sessions), "rawOutcomeCount": len(outcomes),
        "cycleSignalCount": len(cycle_outcomes),
        "holdoutStartDate": holdout_start, "developmentPurgeRule": "Each symbol's 20-session forward endpoint must precede its first holdout observation.",
        "developmentPurgeSessions": 20, "purgedDevelopmentSignals": purged_development_signals,
        "costSensitivityAssumptions": "Hypothetical round-trip cost scenarios of 10/20/30 bps; not actual broker charges.",
        "stats": summarize(cycle_outcomes)["overall"],
        "developmentStats": summarize(development)["overall"],
        "holdoutStats": summarize(holdout)["overall"],
        "holdoutVolatilityRegimeStats": summarize(holdout)["byVolatilityRegime"],
        "rolloverConditionStats": rollover_condition_stats,
        "walkForward": {
            "status": "AVAILABLE" if walk_forward_folds else "INSUFFICIENT_HISTORY",
            "method": "Expanding chronological development window; up to four non-overlapping forward test folds; each fold purges development labels whose symbol-specific 20-session endpoint reaches the test window.",
            "minimumInitialDevelopmentFraction": 0.6,
            "minimumTestDatesPerFold": 5,
            "foldCount": len(walk_forward_folds),
            "evaluatedTestSignals": len(walk_forward_rows),
            "stats": walk_forward_summary,
            "folds": walk_forward_fold_summaries,
        },
        "outcomes": outcomes, "cycleOutcomes": cycle_outcomes,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"Built {OUTPUT}: {len(dates)} sessions, {len(metrics)} symbol/day rollover metrics")
    print(f"Built {OUTCOMES_OUTPUT}: {len(outcomes)} forward outcome rows")
    return result


if __name__ == "__main__":
    build()
