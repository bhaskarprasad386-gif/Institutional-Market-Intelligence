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

DELIVERY_DAY_MIN_COMPARISONS = 100
DELIVERY_DAY_MISMATCH_QUARANTINE_RATE = 0.10


def cash_delivery_day_quality(daily):
    """Quarantine a date when a broad source inconsistency suggests a bad file."""
    comparable = 0
    mismatches = 0
    for delivery in (daily or {}).values():
        source_pct = number(delivery.get("deliveryPct"))
        computed_pct = number(delivery.get("computedDeliveryPct"))
        status = delivery.get("deliveryPctConsistencyStatus")
        if status is None and source_pct is not None and computed_pct is not None:
            status = "MATCH" if abs(source_pct - computed_pct) <= 1.0 else "MISMATCH"
        if status not in ("MATCH", "MISMATCH"):
            continue
        comparable += 1
        mismatches += status == "MISMATCH"
    mismatch_rate = mismatches / comparable if comparable else 0.0
    quarantined = (
        comparable >= DELIVERY_DAY_MIN_COMPARISONS
        and mismatch_rate >= DELIVERY_DAY_MISMATCH_QUARANTINE_RATE
    )
    return {
        "status": "QUARANTINED_SYSTEMIC_MISMATCH" if quarantined else "USABLE",
        "comparableRows": comparable,
        "mismatchRows": mismatches,
        "mismatchRate": mismatch_rate,
    }


def attach_point_in_time_cash_delivery(metrics, archive_by_date):
    """Attach cash demand fields; quarantine dates with systemic source inconsistency."""
    day_quality = {
        market_date: cash_delivery_day_quality(daily)
        for market_date, daily in archive_by_date.items()
    }
    by_symbol = defaultdict(list)
    for row in metrics:
        by_symbol[row["symbol"]].append(row)
    for rows in by_symbol.values():
        rows.sort(key=lambda row: row["tradeDate"])
        for index, row in enumerate(rows):
            daily = archive_by_date.get(row["tradeDate"])
            delivery = daily.get(row["symbol"]) if daily is not None else None
            quality = day_quality.get(row["tradeDate"], {"status": "USABLE"})
            row["cashDeliveryDayQualityStatus"] = quality["status"]
            row["cashDeliveryDayMismatchRate"] = quality.get("mismatchRate")
            if quality["status"] == "QUARANTINED_SYSTEMIC_MISMATCH":
                delivery = None
            row["deliveryPct"] = number(delivery.get("deliveryPct")) if delivery else None
            row["computedDeliveryPct"] = number(delivery.get("computedDeliveryPct")) if delivery else None
            stored_consistency = (
                delivery.get("deliveryPctConsistencyStatus")
                if delivery else None
            )
            # Older archived files predate the explicit consistency-status field,
            # but already contain both source and computed percentages. Re-derive
            # the status from those point-in-time values instead of discarding
            # otherwise verifiable historical delivery data.
            if delivery and stored_consistency is None:
                source_pct = number(delivery.get("deliveryPct"))
                computed_pct = number(delivery.get("computedDeliveryPct"))
                stored_consistency = (
                    "UNVERIFIED" if source_pct is None or computed_pct is None else
                    "MATCH" if abs(source_pct - computed_pct) <= 1.0 else "MISMATCH"
                )
            row["deliveryPctConsistencyStatus"] = (
                stored_consistency if delivery else "ARCHIVE_UNAVAILABLE"
            )
            row["deliveryPctTrusted"] = (
                row["deliveryPct"] if delivery and
                row["deliveryPctConsistencyStatus"] == "MATCH" else None
            )
            row["deliveryCoverageStatus"] = (
                "AVAILABLE" if delivery else
                "SYMBOL_NOT_REPORTED" if daily is not None else
                "DATE_ARCHIVE_MISSING"
            )
            if quality["status"] == "QUARANTINED_SYSTEMIC_MISMATCH":
                row["deliveryCoverageStatus"] = "DATE_DATA_QUALITY_QUARANTINED"
            row["deliveryPctMomentum5d"] = None
            row["deliveryPctTrendQualityStatus"] = "INSUFFICIENT_HISTORY"
            quantities_trusted = bool(
                delivery and row["deliveryPctConsistencyStatus"] == "MATCH"
            )
            row["deliveryQuantity"] = (
                number(delivery.get("deliveryQuantity"))
                if quantities_trusted else None
            )
            row["tradedQuantity"] = (
                number(delivery.get("tradedQuantity"))
                if quantities_trusted else None
            )
            row["cashVwap"] = number(delivery.get("vwap")) if delivery else None
            row["cashClosePrice"] = number(delivery.get("closePrice")) if delivery else None
            row["cashTradedValueProxy"] = (
                row["cashVwap"] * row["tradedQuantity"]
                if row["cashVwap"] is not None and row["tradedQuantity"] is not None else None
            )
            row["vwapStrengthPct"] = (
                (row["cashClosePrice"] / row["cashVwap"] - 1) * 100
                if row["cashClosePrice"] is not None and row["cashVwap"] is not None
                and row["cashVwap"] > 0 else None
            )
            row["cashDemandCoverageStatus"] = (
                "AVAILABLE" if delivery and all(row.get(field) is not None for field in
                    ("deliveryQuantity", "tradedQuantity", "cashVwap", "cashClosePrice"))
                else "PARTIAL_DATA" if delivery else row["deliveryCoverageStatus"]
            )
            for horizon in (5, 20):
                row[f"deliveryQuantityMomentum{horizon}dPct"] = None
                row[f"tradedQuantityMomentum{horizon}dPct"] = None
                row[f"cashTradedValueProxyMomentum{horizon}dPct"] = None
                if index < horizon:
                    continue
                prior = rows[index - horizon]
                for field, output in (
                    ("deliveryQuantity", f"deliveryQuantityMomentum{horizon}dPct"),
                    ("tradedQuantity", f"tradedQuantityMomentum{horizon}dPct"),
                    ("cashTradedValueProxy", f"cashTradedValueProxyMomentum{horizon}dPct"),
                ):
                    current_value = number(row.get(field))
                    prior_value = number(prior.get(field))
                    if current_value is not None and prior_value is not None and prior_value > 0:
                        row[output] = (current_value / prior_value - 1) * 100
            if index >= 5:
                prior = rows[index - 5]
                if (row.get("deliveryPctConsistencyStatus") == "MATCH"
                        and prior.get("deliveryPctConsistencyStatus") == "MATCH"
                        and row.get("deliveryPctTrusted") is not None
                        and prior.get("deliveryPctTrusted") is not None):
                    row["deliveryPctMomentum5d"] = (
                        row["deliveryPctTrusted"] - prior["deliveryPctTrusted"]
                    )
                    row["deliveryPctTrendQualityStatus"] = "TRUSTED_MATCHED_ENDPOINTS"
                elif row.get("deliveryPctConsistencyStatus") != "MATCH":
                    row["deliveryPctTrendQualityStatus"] = "CURRENT_SOURCE_MISMATCH_OR_UNVERIFIED"
                else:
                    row["deliveryPctTrendQualityStatus"] = "PRIOR_SOURCE_MISMATCH_OR_UNVERIFIED"
    return metrics

def load_cash_delivery_history(directory=Path("public/data/nse-cash-delivery")):
    """Load archived NSE cash delivery files keyed by date and symbol."""
    index_path = directory / "index.json"
    if not index_path.exists():
        return {}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    result = {}
    for entry in index.get("dates", []):
        market_date = entry.get("marketDate")
        relative_path = entry.get("path")
        if not market_date or not relative_path:
            continue
        payload_path = directory / relative_path
        if not payload_path.exists():
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if payload.get("marketDate") != market_date:
            raise ValueError(f"Cash delivery archive date mismatch: {relative_path}")
        result[market_date] = {
            row["symbol"]: row for row in payload.get("rows", [])
            if row.get("symbol") and row.get("series") == "EQ"
        }
    return result


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



def add_point_in_time_rollover_zscore(metrics, window=63):
    """Compare today's rollover share with the prior 63 symbol sessions only."""
    by_symbol = defaultdict(list)
    for row in metrics:
        by_symbol[row["symbol"]].append(row)
    for rows in by_symbol.values():
        rows.sort(key=lambda row: row["tradeDate"])
        for index, row in enumerate(rows):
            history = [
                number(item.get("rolloverPct"))
                for item in rows[max(0, index - window):index]
            ]
            history = [value for value in history if value is not None]
            row["rolloverPctMean63d"] = None
            row["rolloverPctStd63d"] = None
            row["rolloverPctZScore63d"] = None
            if len(history) < window:
                row["rolloverZScoreStatus"] = "INSUFFICIENT_63_PRIOR_SESSIONS"
                continue
            mean = sum(history) / window
            variance = sum((value - mean) ** 2 for value in history) / window
            std_dev = math.sqrt(variance)
            row["rolloverPctMean63d"] = mean
            row["rolloverPctStd63d"] = std_dev
            if std_dev <= 1e-12:
                row["rolloverZScoreStatus"] = "ZERO_HISTORICAL_VARIANCE"
                continue
            current = number(row.get("rolloverPct"))
            if current is None:
                row["rolloverZScoreStatus"] = "MISSING_CURRENT_ROLLOVER"
                continue
            row["rolloverPctZScore63d"] = (current - mean) / std_dev
            row["rolloverZScoreStatus"] = "AVAILABLE"
    return metrics

def joint_market_stock_cohorts(rows):
    """Split the core high-rollover/share-down/cost-rising cohort by NIFTY and stock price/OI regimes."""
    cohorts = {}
    for trend in ("DOWN", "UP", "FLAT"):
        for price, oi in (("DOWN", "UP"), ("DOWN", "DOWN"), ("UP", "UP"), ("UP", "DOWN")):
            name = f"HIGH_BOTH_SHARE_DOWN_COST_RISING_NIFTY_{trend}_PRICE_{price}_OI_{oi}"
            cohorts[name] = [
                row for row in rows
                if row.get("rolloverPctFlag") == "HIGH"
                and row.get("rolloverCostFlag") == "HIGH"
                and row.get("nextShareMomentum5d") is not None
                and row["nextShareMomentum5d"] < 0
                and row.get("rolloverCostMomentum5dPct") is not None
                and row["rolloverCostMomentum5dPct"] > 0
                and row.get("niftyTrend5d") == trend
                and row.get("spotMomentum5dPct") is not None
                and (row["spotMomentum5dPct"] < 0 if price == "DOWN" else row["spotMomentum5dPct"] > 0)
                and row.get("totalOiMomentum5dPct") is not None
                and (row["totalOiMomentum5dPct"] > 0 if oi == "UP" else row["totalOiMomentum5dPct"] < 0)
            ]
    return cohorts


def joint_market_stock_share_increase_cohorts(rows):
    """Compare rising next-expiry OI share against the existing falling-share cohorts."""
    cohorts = {}
    for trend in ("DOWN", "UP", "FLAT"):
        for price, oi in (("DOWN", "UP"), ("DOWN", "DOWN"), ("UP", "UP"), ("UP", "DOWN")):
            name = f"HIGH_BOTH_SHARE_UP_COST_RISING_NIFTY_{trend}_PRICE_{price}_OI_{oi}"
            cohorts[name] = [
                row for row in rows
                if row.get("rolloverPctFlag") == "HIGH"
                and row.get("rolloverCostFlag") == "HIGH"
                and row.get("nextShareMomentum5d") is not None
                and row["nextShareMomentum5d"] > 0
                and row.get("rolloverCostMomentum5dPct") is not None
                and row["rolloverCostMomentum5dPct"] > 0
                and row.get("niftyTrend5d") == trend
                and row.get("spotMomentum5dPct") is not None
                and (row["spotMomentum5dPct"] < 0 if price == "DOWN" else row["spotMomentum5dPct"] > 0)
                and row.get("totalOiMomentum5dPct") is not None
                and (row["totalOiMomentum5dPct"] > 0 if oi == "UP" else row["totalOiMomentum5dPct"] < 0)
            ]
    return cohorts



def joint_rollover_zscore_cohorts(rows):
    """Compare high-rollover/high-cost signals with positive and negative 63-session Z-scores."""
    cohorts = {}
    for threshold in (1.5, 2.0):
        label = str(threshold).replace(".", "")
        cohorts[f"HIGH_BOTH_ROLLOVER_ZSCORE_{label}"] = [
            row for row in rows
            if row.get("rolloverPctFlag") == "HIGH"
            and row.get("rolloverCostFlag") == "HIGH"
            and row.get("rolloverZScoreStatus") == "AVAILABLE"
            and row.get("rolloverPctZScore63d") is not None
            and row["rolloverPctZScore63d"] >= threshold
        ]
    # A cross-sectionally high rollover can still be below the same stock's
    # own prior-year norm. Keep these as research cohorts, not entry filters.
    for threshold in (0.25, 0.5, 0.75, 1.0):
        label = str(threshold).replace(".", "")
        cohorts[f"HIGH_BOTH_ROLLOVER_ZSCORE_NEG{label}"] = [
            row for row in rows
            if row.get("rolloverPctFlag") == "HIGH"
            and row.get("rolloverCostFlag") == "HIGH"
            and row.get("rolloverZScoreStatus") == "AVAILABLE"
            and row.get("rolloverPctZScore63d") is not None
            and row["rolloverPctZScore63d"] <= -threshold
        ]
    return cohorts



def false_signal_forensics(rows, threshold_pct=0.5, include_pairwise_interactions=True):
    """Compare correct and failed 20-session Shorts inside the pre-defined core cohort."""
    selected = [
        row for row in rows
        if row.get("rolloverPctFlag") == "HIGH"
        and row.get("rolloverCostFlag") == "HIGH"
        and row.get("nextShareMomentum5d") is not None
        and row["nextShareMomentum5d"] < 0
        and row.get("rolloverCostMomentum5dPct") is not None
        and row["rolloverCostMomentum5dPct"] > 0
        and row.get("nextBuildUp") == "SHORT_BUILD_UP"
    ]
    evaluated = [row for row in selected if row.get("correct20d") is not None]

    def result_stats(sample):
        n = len(sample)
        hits = sum(row.get("correct20d") is True for row in sample)
        net_hits = sum(
            number(row.get("return20dPct")) is not None
            and number(row.get("return20dPct")) <= -(threshold_pct + 0.2)
            for row in sample
        )
        precision = hits / n if n else None
        if n:
            z = 1.96
            denominator = 1 + z * z / n
            center = (precision + z * z / (2 * n)) / denominator
            margin = z * math.sqrt(precision * (1 - precision) / n + z * z / (4 * n * n)) / denominator
            wilson95 = [round(max(0.0, center - margin) * 100, 2),
                        round(min(1.0, center + margin) * 100, 2)]
        else:
            wilson95 = None
        return {
            "evaluated": n, "correct": hits, "wrong": n - hits,
            "precisionPct": round(precision * 100, 2) if n else None,
            "precisionWilson95Pct": wilson95,
            "netPrecision20BpsPct": round(net_hits / n * 100, 2) if n else None,
            "sampleWarning": "LOW_SAMPLE_LT_5" if n < 5 else None,
        }

    def quantiles(values):
        values = sorted(value for value in values if value is not None and math.isfinite(value))
        if not values:
            return {"count": 0, "median": None, "p25": None, "p75": None}
        def percentile(p):
            position = (len(values) - 1) * p
            lower = int(position)
            upper = min(lower + 1, len(values) - 1)
            weight = position - lower
            return round(values[lower] * (1 - weight) + values[upper] * weight, 4)
        return {"count": len(values), "median": percentile(0.5),
                "p25": percentile(0.25), "p75": percentile(0.75)}

    def oi_migration_group(row):
        near = number(row.get("nearOiChange"))
        nxt = number(row.get("nextOiChange"))
        if near is None or nxt is None:
            return "MISSING"
        if near < 0 and nxt > 0:
            return "NEAR_REDUCTION_NEXT_ADDITION_PROXY"
        if near >= 0 and nxt > 0:
            return "NEXT_EXPIRY_OI_ADDITION"
        if near < 0 and nxt < 0:
            return "POSITION_REDUCTION_BOTH"
        return "MIXED_OR_UNCONFIRMED"

    oi_migration_buckets = defaultdict(list)
    for row in selected:
        oi_migration_buckets[oi_migration_group(row)].append(row)
    oi_migration_results = {
        label: {
            "signals": len(bucket),
            **result_stats([row for row in bucket if row.get("correct20d") is not None]),
        }
        for label, bucket in sorted(oi_migration_buckets.items())
    }

    categorical_fields = {
        "niftyTrend5d": lambda row: row.get("niftyTrend5d") or "MISSING",
        "stockPriceTrend5d": lambda row: (
            "MISSING" if row.get("spotMomentum5dPct") is None else
            "UP" if row["spotMomentum5dPct"] > 0.25 else
            "DOWN" if row["spotMomentum5dPct"] < -0.25 else "FLAT"
        ),
        "totalOiTrend5d": lambda row: (
            "MISSING" if row.get("totalOiMomentum5dPct") is None else
            "UP" if row["totalOiMomentum5dPct"] > 0 else
            "DOWN" if row["totalOiMomentum5dPct"] < 0 else "FLAT"
        ),
        "volatilityRegime": lambda row: row.get("volatilityRegime") or "MISSING",
        "deliveryTrend5d": lambda row: (
            "MISSING" if row.get("deliveryPctMomentum5d") is None else
            "UP" if row["deliveryPctMomentum5d"] > 1.0 else
            "DOWN" if row["deliveryPctMomentum5d"] < -1.0 else "FLAT"
        ),
    }
    subgroup_results = {}
    for field, classify in categorical_fields.items():
        buckets = defaultdict(list)
        for row in selected:
            buckets[classify(row)].append(row)
        subgroup_results[field] = {
            label: {
                "signals": len(bucket),
                **result_stats([row for row in bucket if row.get("correct20d") is not None]),
            }
            for label, bucket in sorted(buckets.items())
        }

    # Pairwise interaction tables are diagnostic only. They are computed
    # from the pre-defined cohort and never alter signal eligibility or direction.
    interaction_pairs = (
        ("niftyTrend5d", "stockPriceTrend5d"),
        ("stockPriceTrend5d", "totalOiTrend5d"),
        ("stockPriceTrend5d", "volatilityRegime"),
    )

    def interaction_label(row, field):
        if field == "niftyTrend5d":
            return row.get(field) or "MISSING"
        if field == "stockPriceTrend5d":
            value = number(row.get("spotMomentum5dPct"))
            return (
                "MISSING" if value is None else
                "UP" if value > 0.25 else
                "DOWN" if value < -0.25 else "FLAT"
            )
        if field == "totalOiTrend5d":
            value = number(row.get("totalOiMomentum5dPct"))
            return (
                "MISSING" if value is None else
                "UP" if value > 0 else
                "DOWN" if value < 0 else "FLAT"
            )
        return row.get(field) or "MISSING"

    def is_core_rollover_cohort(row):
        return (
            row.get("rolloverPctFlag") == "HIGH"
            and row.get("rolloverCostFlag") == "HIGH"
            and row.get("nextShareMomentum5d") is not None
            and row["nextShareMomentum5d"] < 0
            and row.get("rolloverCostMomentum5dPct") is not None
            and row["rolloverCostMomentum5dPct"] > 0
            and row.get("nextBuildUp") == "SHORT_BUILD_UP"
        )

    pairwise_interactions = {}
    matched_baseline_comparisons = {}
    if include_pairwise_interactions:
        for left_field, right_field in interaction_pairs:
            cells = defaultdict(list)
            for row in evaluated:
                cells[(interaction_label(row, left_field),
                       interaction_label(row, right_field))].append(row)
            cell_results = []
            for (left_label, right_label), sample in sorted(cells.items()):
                stats = result_stats(sample)
                cell_results.append({
                    "left": left_label,
                    "right": right_label,
                    **stats,
                })
            pairwise_interactions[f"{left_field}__{right_field}"] = {
                "leftField": left_field,
                "rightField": right_field,
                "evaluatedSignals": len(evaluated),
                "cells": cell_results,
                "interpretation": (
                    "EXPLORATORY_ONLY; DEVELOPMENT_ONLY; cells below 5 evaluated "
                    "signals are low-sample; no filter or entry rule is implied."
                ),
            }

            if (left_field, right_field) == ("niftyTrend5d", "stockPriceTrend5d"):
                baseline_cells = defaultdict(list)
                cohort_cells = defaultdict(list)
                for row in rows:
                    if (row.get("nextBuildUp") == "SHORT_BUILD_UP"
                            and row.get("correct20d") is not None
                            and not is_core_rollover_cohort(row)):
                        key = (interaction_label(row, left_field),
                               interaction_label(row, right_field))
                        baseline_cells[key].append(row)
                for row in evaluated:
                    key = (interaction_label(row, left_field),
                           interaction_label(row, right_field))
                    cohort_cells[key].append(row)
                comparisons = []
                for key in sorted(set(baseline_cells) | set(cohort_cells)):
                    cohort_stats = result_stats(cohort_cells.get(key, []))
                    baseline_stats = result_stats(baseline_cells.get(key, []))
                    lift = (
                        round(cohort_stats["precisionPct"] - baseline_stats["precisionPct"], 2)
                        if cohort_stats["precisionPct"] is not None
                        and baseline_stats["precisionPct"] is not None else None
                    )
                    comparisons.append({
                        "niftyTrend5d": key[0],
                        "stockPriceTrend5d": key[1],
                        "cohort": cohort_stats,
                        "matchedNonCohortShortBaseline": baseline_stats,
                        "precisionLiftPercentagePoints": lift,
                        "warning": (
                            "LOW_SAMPLE_OR_MISSING_COMPARATOR"
                            if cohort_stats["evaluated"] < 5
                            or baseline_stats["evaluated"] < 5 else None
                        ),
                    })
                matched_baseline_comparisons["niftyTrend5d__stockPriceTrend5d"] = {
                    "baselineDefinition": (
                        "Other SHORT_BUILD_UP rows excluding the core rollover cohort, "
                        "matched on identical NIFTY and stock-price trend labels."
                    ),
                    "cells": comparisons,
                    "interpretation": (
                        "DEVELOPMENT_ONLY_DIAGNOSTIC; positive lift is not proof; "
                        "do not select a trading filter from this same-sample comparison."
                    ),
                }

    numeric_fields = (
        "nearOiChange", "nextOiChange",
        "rolloverPct", "rolloverCostPct", "nextShareMomentum5d",
        "rolloverCostMomentum5dPct", "spotMomentum5dPct",
        "totalOiMomentum5dPct", "niftyMomentum5dPct",
        "realizedVol20dAnnualizedPct",
        "deliveryPct", "deliveryPctMomentum5d", "deliveryQuantity",
        "deliveryQuantityMomentum5dPct", "deliveryQuantityMomentum20dPct",
        "tradedQuantity", "tradedQuantityMomentum5dPct", "tradedQuantityMomentum20dPct",
        "cashTradedValueProxy", "cashTradedValueProxyMomentum5dPct",
        "cashTradedValueProxyMomentum20dPct", "vwapStrengthPct",
    )
    feature_comparison = {
        field: {
            "correct": quantiles([number(row.get(field)) for row in evaluated if row.get("correct20d") is True]),
            "wrong": quantiles([number(row.get(field)) for row in evaluated if row.get("correct20d") is False]),
        }
        for field in numeric_fields
    }
    return {
        "cohortDefinition": "HIGH rollover + HIGH positive roll cost + falling next-expiry OI share + rising roll cost over 5 sessions + SHORT_BUILD_UP",
        "target": f"20-session return <= -{threshold_pct:.2f}% is a correct Short; net 20bps hit requires return <= -{(threshold_pct + 0.2):.2f}%",
        "signals": len(selected), "evaluated": len(evaluated),
        "correct": sum(row.get("correct20d") is True for row in evaluated),
        "wrong": sum(row.get("correct20d") is False for row in evaluated),
        "flatExcluded": sum(row.get("outcome20d") == "FLAT" for row in selected),
        "pending": sum(row.get("outcome20d") == "PENDING" for row in selected),
        "overall": result_stats(evaluated), "subgroups": subgroup_results,
        "oiMigrationGroups": oi_migration_results,
        "pairwiseInteractions": pairwise_interactions,
        "matchedBaselineComparisons": matched_baseline_comparisons,
        "correctVsWrongFeatureDistributions": feature_comparison,
        "signalDetails": [
            {
                "symbol": row.get("symbol"), "signalDate": row.get("signalDate"),
                "correct20d": row.get("correct20d"), "outcome20d": row.get("outcome20d"),
                "return20dPct": number(row.get("return20dPct")),
                "niftyTrend5d": row.get("niftyTrend5d"),
                "spotMomentum5dPct": number(row.get("spotMomentum5dPct")),
                "totalOiMomentum5dPct": number(row.get("totalOiMomentum5dPct")),
                "nearOiChange": number(row.get("nearOiChange")),
                "nextOiChange": number(row.get("nextOiChange")),
                "oiMigrationGroup": oi_migration_group(row),
                "rolloverPct": number(row.get("rolloverPct")),
                "rolloverCostPct": number(row.get("rolloverCostPct")),
                "nextShareMomentum5d": number(row.get("nextShareMomentum5d")),
                "rolloverCostMomentum5dPct": number(row.get("rolloverCostMomentum5dPct")),
                "volatilityRegime": row.get("volatilityRegime"),
                "deliveryPct": number(row.get("deliveryPct")),
                "deliveryPctMomentum5d": number(row.get("deliveryPctMomentum5d")),
                "deliveryCoverageStatus": row.get("deliveryCoverageStatus"),
            }
            for row in selected
        ],
        "interpretationGuard": "Exploratory diagnosis only; do not convert same-sample subgroup results into a trading filter. Wilson intervals describe sampling uncertainty and do not correct regime shift or selection bias. Require newly accrued prospective validation.",
    }

def cohort_evidence_gate(selected, summary):
    """Apply a conservative sample/breadth gate before highlighting 20-session accuracy."""
    breadth = {
        "symbols": len({row.get("symbol") for row in selected if row.get("symbol")}),
        "dates": len({row.get("signalDate") for row in selected if row.get("signalDate")}),
    }
    total = len(selected)
    symbol_counts = defaultdict(int)
    date_counts = defaultdict(int)
    for row in selected:
        symbol_counts[row.get("symbol")] += 1
        date_counts[row.get("signalDate")] += 1
    breadth["maxSymbolSharePct"] = round(max(symbol_counts.values(), default=0) / total * 100, 2) if total else None
    breadth["maxDateSharePct"] = round(max(date_counts.values(), default=0) / total * 100, 2) if total else None
    short = summary.get("SHORT_BUILD_UP_20D", {})
    evaluated = short.get("evaluatedSignals", 0)
    reasons = []
    if evaluated < 30:
        reasons.append("FEWER_THAN_30_EVALUATED_SHORT_20D")
    if breadth["symbols"] < 10:
        reasons.append("FEWER_THAN_10_SYMBOLS")
    if breadth["dates"] < 8:
        reasons.append("FEWER_THAN_8_SIGNAL_DATES")
    if breadth["maxSymbolSharePct"] is None or breadth["maxSymbolSharePct"] > 20:
        reasons.append("SINGLE_SYMBOL_CONCENTRATION_OVER_20_PERCENT")
    if breadth["maxDateSharePct"] is None or breadth["maxDateSharePct"] > 20:
        reasons.append("SINGLE_DATE_CONCENTRATION_OVER_20_PERCENT")
    net20 = short.get("costSensitivity", {}).get("20", {}).get("netPrecisionPct")
    precision = short.get("precisionPct")
    passed = not reasons
    return {
        "status": "BREADTH_OK_NOT_PROOF" if passed else "INSUFFICIENT_EVIDENCE",
        "minimums": {"evaluatedShort20d": 30, "uniqueSymbols": 10, "uniqueSignalDates": 8,
                     "maxSingleSymbolSharePct": 20, "maxSingleDateSharePct": 20},
        "breadth": breadth,
        "evaluatedShort20d": evaluated,
        "short20dPrecisionPct": precision,
        "short20dNetPrecision20BpsPct": net20,
        "meets80PercentAfter20BpsGate": bool(passed and precision is not None and net20 is not None
                                              and precision >= 80 and net20 >= 80),
        "failedChecks": reasons,
    }


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

    cash_delivery_history = load_cash_delivery_history()
    metrics = attach_point_in_time_cash_delivery(metrics, cash_delivery_history)
    metrics = apply_daily_rollover_flags(metrics)
    metrics = add_point_in_time_rollover_momentum(metrics)
    metrics = add_point_in_time_rollover_zscore(metrics, window=63)
    metrics = add_point_in_time_market_momentum(metrics, nifty_spot_by_date, horizon=5)
    result = {
        "source": "Derived from complete NSE F&O dated history archive",
        "updatedAt": index.get("updatedAt"),
        "archivedSessions": len(dates),
        "oldestMarketDate": min((x["marketDate"] for x in dates), default=None),
        "newestMarketDate": max((x["marketDate"] for x in dates), default=None),
        "metricCount": len(metrics),
        "cashDeliveryCoverage": {
            "archivedDates": len(cash_delivery_history),
            "availableMetricRows": sum(row.get("deliveryCoverageStatus") == "AVAILABLE" for row in metrics),
            "missingDateRows": sum(row.get("deliveryCoverageStatus") == "DATE_ARCHIVE_MISSING" for row in metrics),
            "missingSymbolRows": sum(row.get("deliveryCoverageStatus") == "SYMBOL_NOT_REPORTED" for row in metrics),
            "quarantinedMetricRows": sum(row.get("deliveryCoverageStatus") == "DATE_DATA_QUALITY_QUARANTINED" for row in metrics),
            "quarantinedDates": len({row.get("tradeDate") for row in metrics
                                     if row.get("cashDeliveryDayQualityStatus") == "QUARANTINED_SYSTEMIC_MISMATCH"}),
            "status": "AVAILABLE" if cash_delivery_history else "NOT_ARCHIVED",
        },
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
                "nearOiChange": row.get("nearOiChange"), "nextOiChange": row.get("nextOiChange"),
                "rolloverPct": row["rolloverPct"], "rolloverCostPct": row["rolloverCostPct"],
                "rolloverPctFlag": row["rolloverPctFlag"], "rolloverCostFlag": row["rolloverCostFlag"],
                "rolloverZScoreStatus": row.get("rolloverZScoreStatus"),
                "rolloverPctMean63d": row.get("rolloverPctMean63d"),
                "rolloverPctStd63d": row.get("rolloverPctStd63d"),
                "rolloverPctZScore63d": row.get("rolloverPctZScore63d"),
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
                    symbol_spot_series, row["symbol"], row["tradeDate"], 5),
                "deliveryPct": row.get("deliveryPct"),
                "computedDeliveryPct": row.get("computedDeliveryPct"),
                "deliveryPctTrusted": row.get("deliveryPctTrusted"),
                "deliveryPctConsistencyStatus": row.get("deliveryPctConsistencyStatus"),
                "deliveryPctTrendQualityStatus": row.get("deliveryPctTrendQualityStatus"),
                "deliveryPctMomentum5d": row.get("deliveryPctMomentum5d"),
                "deliveryQuantity": row.get("deliveryQuantity"),
                "deliveryQuantityMomentum5dPct": row.get("deliveryQuantityMomentum5dPct"),
                "deliveryQuantityMomentum20dPct": row.get("deliveryQuantityMomentum20dPct"),
                "tradedQuantity": row.get("tradedQuantity"),
                "tradedQuantityMomentum5dPct": row.get("tradedQuantityMomentum5dPct"),
                "tradedQuantityMomentum20dPct": row.get("tradedQuantityMomentum20dPct"),
                "cashTradedValueProxy": row.get("cashTradedValueProxy"),
                "cashTradedValueProxyMomentum5dPct": row.get("cashTradedValueProxyMomentum5dPct"),
                "cashTradedValueProxyMomentum20dPct": row.get("cashTradedValueProxyMomentum20dPct"),
                "vwapStrengthPct": row.get("vwapStrengthPct"),
                "cashDemandCoverageStatus": row.get("cashDemandCoverageStatus", "DATE_ARCHIVE_MISSING"),
                "deliveryCoverageStatus": row.get("deliveryCoverageStatus", "DATE_ARCHIVE_MISSING"),
                "cashDeliveryDayQualityStatus": row.get("cashDeliveryDayQualityStatus", "UNVERIFIED"),
                "cashDeliveryDayMismatchRate": row.get("cashDeliveryDayMismatchRate")}
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
            **joint_rollover_zscore_cohorts(rows),
            **joint_market_stock_cohorts(rows),
            **joint_market_stock_share_increase_cohorts(rows),
        }
        return {
            name: {
                "signalCount": len(selected),
                "breadth": cohort_breadth(selected),
                "stats": summarize(selected)["overall"],
                "evidenceGate": cohort_evidence_gate(selected, summarize(selected)["overall"]),
                # Regime labels use only prior symbol-session spot returns.
                # Keep the same cohort definitions across holdout and each fold.
                "byVolatilityRegime": summarize(selected)["byVolatilityRegime"],
            }
            for name, selected in cohorts.items()
        }

    def rollover_zscore_diagnostics(rows):
        status_counts = {}
        for row in rows:
            status = row.get("rolloverZScoreStatus") or "MISSING_STATUS"
            status_counts[status] = status_counts.get(status, 0) + 1
        available = [
            row for row in rows
            if row.get("rolloverZScoreStatus") == "AVAILABLE"
            and row.get("rolloverPctZScore63d") is not None
        ]
        high_both = [
            row for row in available
            if row.get("rolloverPctFlag") == "HIGH"
            and row.get("rolloverCostFlag") == "HIGH"
        ]
        z_values = sorted(row["rolloverPctZScore63d"] for row in high_both)
        def percentile(values, pct):
            if not values:
                return None
            position = (len(values) - 1) * pct
            lower = int(position)
            upper = min(lower + 1, len(values) - 1)
            weight = position - lower
            return round(values[lower] * (1 - weight) + values[upper] * weight, 4)
        return {
            "rows": len(rows),
            "statusCounts": status_counts,
            "availableZScoreRows": len(available),
            "availableHighBothRows": len(high_both),
            "highBothZScoreDistribution": {
                "min": round(z_values[0], 4) if z_values else None,
                "p50": percentile(z_values, 0.50),
                "p75": percentile(z_values, 0.75),
                "p90": percentile(z_values, 0.90),
                "p95": percentile(z_values, 0.95),
                "max": round(z_values[-1], 4) if z_values else None,
                "positiveCount": sum(value > 0 for value in z_values),
            },
            "highBothZScoreAtLeast05": sum(value >= 0.5 for value in z_values),
            "highBothZScoreAtLeast10": sum(value >= 1.0 for value in z_values),
            "highBothZScoreAtLeast15": sum(value >= 1.5 for value in z_values),
            "highBothZScoreAtLeast20": sum(value >= 2.0 for value in z_values),
        }

    rollover_condition_stats = {
        "flagMethod": "Same-day cross-sectional 75th percentile, matching live scanner; at least 5 total peers and 5 positive-cost peers. No future observations are used.",
        "momentumMethod": "Point-in-time 3/5 symbol-session change in next-expiry OI share (percentage points), total near+next+far OI (percent), and rollover cost (percentage points); current day compared only with prior archived symbol sessions.",
        "marketTrendMethod": "NIFTY spot-close return over the signal date and five prior archived NIFTY sessions; UP above +0.25%, DOWN below -0.25%, otherwise FLAT. Missing index history is kept separate. No future index observations are used.",
        "rolloverZScoreDiagnostics": {"allCycleSignals": rollover_zscore_diagnostics(cycle_outcomes), "holdout": rollover_zscore_diagnostics(holdout), "walkForward": rollover_zscore_diagnostics(walk_forward_rows)},
        "falseSignalForensics": {
            "development": false_signal_forensics(development, threshold_pct),
            "holdout": false_signal_forensics(holdout, threshold_pct, include_pairwise_interactions=False),
            "walkForward": false_signal_forensics(walk_forward_rows, threshold_pct, include_pairwise_interactions=False),
            "walkForwardFolds": [
                {"fold": fold["fold"], "testStartDate": fold["testStartDate"],
                 "testEndDate": fold["testEndDate"],
                 "analysis": false_signal_forensics(fold["testRows"], threshold_pct, include_pairwise_interactions=False)}
                for fold in walk_forward_folds
            ],
        },
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
