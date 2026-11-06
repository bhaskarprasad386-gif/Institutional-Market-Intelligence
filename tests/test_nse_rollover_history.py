import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.nse import build_rollover_history as builder


class RolloverHistoryBuilderTests(unittest.TestCase):
    def test_daily_high_rollover_and_cost_flags_match_live_cross_sectional_thresholds(self):
        rows = [
            {"symbol": f"S{i}", "tradeDate": "2026-01-01",
             "rolloverPct": value, "rolloverCostPct": cost}
            for i, (value, cost) in enumerate([
                (10, 0.10), (20, 0.20), (30, 0.30), (40, 0.40), (50, 0.50)
            ])
        ]
        flagged = {row["symbol"]: row for row in builder.apply_daily_rollover_flags(rows)}
        self.assertEqual(flagged["S2"]["rolloverPctFlag"], "NORMAL")
        self.assertEqual(flagged["S3"]["rolloverPctFlag"], "HIGH")
        self.assertEqual(flagged["S3"]["rolloverCostFlag"], "HIGH")
        self.assertEqual(flagged["S4"]["rolloverPctFlag"], "HIGH")
        self.assertEqual(flagged["S4"]["rolloverCostFlag"], "HIGH")
        self.assertEqual(flagged["S4"]["peerCount"], 5)

        insufficient = builder.apply_daily_rollover_flags(rows[:4])
        self.assertTrue(all(row["rolloverPctFlag"] == "INSUFFICIENT_PEERS" for row in insufficient))
        self.assertTrue(all(row["rolloverCostFlag"] == "INSUFFICIENT_PEERS" for row in insufficient))


    def test_builds_metrics_for_every_indexed_session_and_uses_oi_weighted_prices(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dates = [
                {"marketDate": "2026-01-01", "path": "2026-01-01.json"},
                {"marketDate": "2026-01-02", "path": "2026-01-02.json"},
            ]
            (root / "index.json").write_text(json.dumps({"count": 2, "updatedAt": "now", "dates": dates}))
            for market_date in ("2026-01-01", "2026-01-02"):
                rows = [
                    {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-01-29", "futuresClose": "100", "openInterest": "10", "lotSize": "25"},
                    {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-01-29", "futuresClose": "110", "openInterest": "30", "lotSize": "25"},
                    {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-02-26", "futuresClose": "120", "openInterest": "20", "lotSize": "25"},
                    {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-02-26", "futuresClose": "130", "openInterest": "20", "lotSize": "25"},
                    {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2025-12-25", "futuresClose": "90", "openInterest": "100", "lotSize": "25"},
                ]
                (root / f"{market_date}.json").write_text(json.dumps({"marketDate": market_date, "rows": rows}))
            with patch.object(builder, "ROOT", root), patch.object(builder, "OUTPUT", root / "rollover-metrics.json"), patch.object(builder, "OUTCOMES_OUTPUT", root / "rollover-outcomes.json"):
                result = builder.build()
            self.assertEqual(result["archivedSessions"], 2)
            self.assertEqual(result["metricCount"], 2)
            first = result["metrics"][0]
            self.assertEqual(first["nearExpiry"], "2026-01-29")
            self.assertEqual(first["nextExpiry"], "2026-02-26")
            self.assertAlmostEqual(first["nearFuturesClose"], 107.5)
            self.assertAlmostEqual(first["nextFuturesClose"], 125)
            self.assertAlmostEqual(first["rolloverPct"], 50)
            self.assertEqual(first["lotSize"], 25)
            self.assertTrue((root / "rollover-metrics.json").exists())


    def test_omits_per_lot_cost_when_selected_expiry_has_mixed_lot_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            market_date = "2026-01-01"
            dates = [{"marketDate": market_date, "path": f"{market_date}.json"}]
            (root / "index.json").write_text(json.dumps({"count": 1, "dates": dates}))
            rows = [
                {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-01-29", "futuresClose": "100", "openInterest": "10", "lotSize": "25"},
                {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-01-29", "futuresClose": "101", "openInterest": "20", "lotSize": "50"},
                {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-02-26", "futuresClose": "102", "openInterest": "15", "lotSize": "25"},
            ]
            (root / f"{market_date}.json").write_text(json.dumps({"marketDate": market_date, "rows": rows}))
            with patch.object(builder, "ROOT", root), patch.object(builder, "OUTPUT", root / "rollover-metrics.json"), patch.object(builder, "OUTCOMES_OUTPUT", root / "rollover-outcomes.json"):
                result = builder.build()
            metric = result["metrics"][0]
            self.assertNotIn("lotSize", metric)
            self.assertNotIn("rolloverCostPerLot", metric)


    def test_builds_three_expiry_positioning_and_daily_directional_oi_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            market_date = "2026-01-02"
            dates = [{"marketDate": market_date, "path": f"{market_date}.json"}]
            (root / "index.json").write_text(json.dumps({"count": 1, "dates": dates}))
            rows = [
                {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-01-29", "futuresClose": "105", "previousFuturesClose": "100", "openInterest": "90", "changeOpenInterest": "10", "volume": "100", "lotSize": "25"},
                {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-02-26", "futuresClose": "108", "previousFuturesClose": "102", "openInterest": "80", "changeOpenInterest": "20", "volume": "80", "lotSize": "25"},
                {"symbol": "ABC", "tradeDate": market_date, "expiryDate": "2026-03-26", "futuresClose": "110", "previousFuturesClose": "104", "openInterest": "30", "changeOpenInterest": "5", "volume": "20", "lotSize": "25"},
            ]
            (root / f"{market_date}.json").write_text(json.dumps({"marketDate": market_date, "rows": rows}))
            with patch.object(builder, "ROOT", root), patch.object(builder, "OUTPUT", root / "rollover-metrics.json"), patch.object(builder, "OUTCOMES_OUTPUT", root / "rollover-outcomes.json"):
                result = builder.build()
            metric = result["metrics"][0]
            self.assertEqual(metric["farExpiry"], "2026-03-26")
            self.assertEqual(metric["farOi"], 30)
            self.assertAlmostEqual(metric["extendedRolloverPct"], 110 / 200 * 100)
            self.assertEqual(metric["nearOiChange"], 10)
            self.assertEqual(metric["nextOiChange"], 20)
            self.assertEqual(metric["farOiChange"], 5)
            self.assertEqual(metric["totalOiChange"], 35)
            self.assertEqual(metric["nearBuildUp"], "LONG_BUILD_UP")
            self.assertEqual(metric["nextBuildUp"], "LONG_BUILD_UP")
            self.assertEqual(metric["nearVolume"], 100)
            self.assertEqual(metric["nextVolume"], 80)


    def test_builds_forward_outcomes_without_counting_flat_returns_as_directional_hits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dates = [f"2026-01-{day:02d}" for day in range(1, 8)]
            index_dates = [{"marketDate": day, "path": f"{day}.json"} for day in reversed(dates)]
            (root / "index.json").write_text(json.dumps({"count": len(dates), "dates": index_dates}))
            for i, day in enumerate(dates):
                spot = 100 + (2 if i >= 5 else 0)
                rows = [
                    {"symbol": "ABC", "tradeDate": day, "expiryDate": "2026-01-29", "futuresClose": str(100+i), "previousFuturesClose": str(99+i), "spotClose": str(spot), "openInterest": "100", "changeOpenInterest": "10", "volume": "100", "lotSize": "25"},
                    {"symbol": "ABC", "tradeDate": day, "expiryDate": "2026-02-26", "futuresClose": str(102+i), "previousFuturesClose": str(101+i), "spotClose": str(spot), "openInterest": "100", "changeOpenInterest": "10", "volume": "80", "lotSize": "25"},
                ]
                (root / f"{day}.json").write_text(json.dumps({"marketDate": day, "rows": rows}))
            with patch.object(builder, "ROOT", root), patch.object(builder, "OUTPUT", root / "rollover-metrics.json"), patch.object(builder, "OUTCOMES_OUTPUT", root / "rollover-outcomes.json"):
                result = builder.build()
            outcomes = json.loads((root / "rollover-outcomes.json").read_text())
            first = next(x for x in outcomes["outcomes"] if x["signalDate"] == dates[0])
            self.assertEqual(first["outcome5d"], "UP")
            self.assertAlmostEqual(first["return5dPct"], 2.0)
            self.assertTrue(first["correct5d"])
            self.assertEqual(first["outcome10d"], "PENDING")
            self.assertEqual(outcomes["stats"]["LONG_BUILD_UP_5D"]["evaluatedSignals"], 1)
            self.assertEqual(outcomes["cycleSignalCount"], 1)
            self.assertEqual(len(outcomes["cycleOutcomes"]), 1)
            self.assertIn("20", outcomes["stats"]["LONG_BUILD_UP_5D"]["costSensitivity"])
            self.assertEqual(outcomes["costSensitivityAssumptions"].startswith("Hypothetical"), True)
            self.assertIn("INSUFFICIENT_HISTORY", outcomes["holdoutVolatilityRegimeStats"])
            cohort = outcomes["rolloverConditionStats"]["development"]["ALL_DIRECTIONAL"]
            self.assertIn("byVolatilityRegime", cohort)
            self.assertIn("INSUFFICIENT_HISTORY", cohort["byVolatilityRegime"])
            self.assertEqual(
                cohort["byVolatilityRegime"]["INSUFFICIENT_HISTORY"]["LONG_BUILD_UP_5D"]["evaluatedSignals"],
                1,
            )
            self.assertTrue((root / "rollover-metrics.json").exists())


    def test_forward_returns_use_each_symbols_own_sessions_and_cost_sensitivity_thresholds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dates = [f"2026-02-{day:02d}" for day in range(1, 13)]
            index_dates = [{"marketDate": day, "path": f"{day}.json"} for day in reversed(dates)]
            (root / "index.json").write_text(json.dumps({"count": len(dates), "dates": index_dates}))
            for i, day in enumerate(dates):
                rows = []
                # ABC trades every archived session; XYZ trades only on even-indexed sessions.
                for symbol, include in (("ABC", True), ("XYZ", i % 2 == 0)):
                    if not include:
                        continue
                    spot = 100.6 if symbol == "XYZ" and i == 10 else 100.0
                    for expiry, offset in (("2026-03-26", 0), ("2026-04-30", 2)):
                        rows.append({
                            "symbol": symbol, "tradeDate": day, "expiryDate": expiry,
                            "futuresClose": str(100 + i + offset),
                            "previousFuturesClose": str(99 + i + offset),
                            "spotClose": str(spot), "openInterest": "100",
                            "changeOpenInterest": "10", "volume": "100", "lotSize": "25",
                        })
                (root / f"{day}.json").write_text(json.dumps({"marketDate": day, "rows": rows}))
            with patch.object(builder, "ROOT", root), patch.object(builder, "OUTPUT", root / "rollover-metrics.json"), patch.object(builder, "OUTCOMES_OUTPUT", root / "rollover-outcomes.json"):
                builder.build()
            outcomes = json.loads((root / "rollover-outcomes.json").read_text())
            xyz = next(x for x in outcomes["outcomes"] if x["symbol"] == "XYZ" and x["signalDate"] == dates[0])
            # XYZ's sixth observation is global session 11, not session 6.
            self.assertAlmostEqual(xyz["return5dPct"], 0.6)
            self.assertEqual(xyz["outcome5d"], "UP")
            self.assertEqual(xyz["correct5d"], True)
            long_stats = outcomes["stats"]["LONG_BUILD_UP_5D"]["costSensitivity"]
            self.assertEqual(long_stats["10"]["netDirectionalHits"], 1)
            self.assertEqual(long_stats["20"]["netDirectionalHits"], 0)
            self.assertEqual(long_stats["30"]["netDirectionalHits"], 0)


    def test_development_purge_uses_symbol_sessions_and_strict_twenty_session_boundary(self):
        symbol_days = [f"2026-01-{day:02d}" for day in range(1, 32)]
        holdout_start = symbol_days[25]
        signals = [
            {"symbol": "ABC", "signalDate": symbol_days[4]},  # endpoint index 24: retained
            {"symbol": "ABC", "signalDate": symbol_days[5]},  # endpoint index 25: purged
            {"symbol": "XYZ", "signalDate": symbol_days[4]},  # missing own calendar: purged
            {"symbol": "ABC", "signalDate": holdout_start},  # holdout, not development
        ]
        development, purged = builder.purge_development_signals(
            signals, {"ABC": symbol_days}, holdout_start
        )
        self.assertEqual([x["signalDate"] for x in development], [symbol_days[4]])
        self.assertEqual(purged, 2)

    def test_prior_spot_momentum_uses_signal_close_and_prior_symbol_sessions_only(self):
        series = {"ABC": [
            ("2026-01-01", 100.0), ("2026-01-02", 101.0),
            ("2026-01-03", 102.0), ("2026-01-04", 103.0),
            ("2026-01-05", 104.0), ("2026-01-06", 105.0),
            ("2026-01-07", 106.0),
        ]}
        result = builder.calculate_prior_spot_momentum(series, "ABC", "2026-01-06", 5)
        self.assertAlmostEqual(result, 5.0)
        series["ABC"].append(("2026-01-08", 1000.0))
        self.assertAlmostEqual(
            builder.calculate_prior_spot_momentum(series, "ABC", "2026-01-06", 5), 5.0
        )
        self.assertIsNone(
            builder.calculate_prior_spot_momentum(series, "ABC", "2026-01-05", 5)
        )


    def test_prior_volatility_excludes_signal_day_and_uses_documented_regime_bands(self):
        days = [f"2026-01-{day:02d}" for day in range(1, 24)]
        low_prices = [(day, 100.0 + index * 0.01) for index, day in enumerate(days[:21])]
        low_with_signal_spike = low_prices + [(days[21], 10000.0)]
        low_a = builder.calculate_prior_volatility(
            {"ABC": low_prices}, "ABC", days[21]
        )
        low_b = builder.calculate_prior_volatility(
            {"ABC": low_with_signal_spike}, "ABC", days[21]
        )
        self.assertEqual(low_a, low_b)
        self.assertEqual(low_a[1], "LOW")

        def alternating_series(amplitude):
            prices = [100.0]
            for index in range(20):
                prices.append(prices[-1] * (1 + (amplitude if index % 2 == 0 else -amplitude)))
            return list(zip(days[:21], prices))

        _, medium_regime = builder.calculate_prior_volatility(
            {"ABC": alternating_series(0.02)}, "ABC", days[21]
        )
        _, high_regime = builder.calculate_prior_volatility(
            {"ABC": alternating_series(0.05)}, "ABC", days[21]
        )
        self.assertEqual(medium_regime, "MEDIUM")
        self.assertEqual(high_regime, "HIGH")

    def test_prior_volatility_requires_at_least_ten_prior_returns(self):
        short_history = [(f"2026-01-{day:02d}", 100 + day) for day in range(1, 11)]
        result = builder.calculate_prior_volatility(
            {"ABC": short_history}, "ABC", "2026-01-11"
        )
        self.assertEqual(result, (None, "INSUFFICIENT_HISTORY"))


    def test_no_holdout_partition_keeps_cycle_rows_in_development(self):
        rows = [
            {"symbol": "ABC", "signalDate": "2026-01-05"},
            {"symbol": "XYZ", "signalDate": "2026-01-06"},
        ]
        development, purged = builder.purge_development_signals(
            rows, {"ABC": ["2026-01-05"], "XYZ": ["2026-01-06"]}, None
        )
        self.assertEqual(development, rows)
        self.assertEqual(purged, 0)


    def test_walk_forward_folds_are_chronological_non_overlapping_and_purged(self):
        days = [f"2026-01-{day:02d}" for day in range(1, 31)]
        rows = [
            {"symbol": "ABC", "signalDate": day, "nextBuildUp": "LONG_BUILD_UP"}
            for day in days
        ]
        folds = builder.build_walk_forward_folds(rows, {"ABC": days})
        self.assertGreaterEqual(len(folds), 2)
        self.assertEqual(folds[0]["testStartDate"], days[18])
        for index, fold in enumerate(folds):
            self.assertGreaterEqual(fold["developmentSignalsAfterPurge"], 0)
            self.assertGreaterEqual(fold["purgedDevelopmentSignals"], 0)
            self.assertTrue(all(fold["testStartDate"] <= row["signalDate"] <= fold["testEndDate"] for row in fold["testRows"]))
            if index:
                self.assertGreater(fold["testStartDate"], folds[index - 1]["testEndDate"])
        # The first development signal is purged when its 20-session endpoint
        # reaches the first test observation.
        first = folds[0]
        self.assertNotEqual(first["developmentSignalsAfterPurge"], len(rows[:18]))

    def test_walk_forward_requires_minimum_out_of_sample_history(self):
        days = [f"2026-01-{day:02d}" for day in range(1, 10)]
        rows = [{"symbol": "ABC", "signalDate": day} for day in days]
        self.assertEqual(builder.build_walk_forward_folds(rows, {"ABC": days}), [])


    def test_point_in_time_rollover_momentum_uses_prior_symbol_sessions_only(self):
        rows = []
        for index in range(7):
            rows.append({
                "symbol": "ABC", "tradeDate": f"2026-01-{index + 1:02d}",
                "nearOi": 100 - index * 5, "nextOi": 100 + index * 5,
                "totalOi": 200 + index * 10, "rolloverCostPct": 0.10 + index * 0.01,
            })
        result = builder.add_point_in_time_rollover_momentum(rows)
        self.assertIsNone(result[2]["nextShareMomentum3d"])
        self.assertAlmostEqual(result[3]["nextShareMomentum3d"], 7.5)
        self.assertAlmostEqual(result[5]["nextShareMomentum5d"], 12.5)
        self.assertAlmostEqual(result[5]["totalOiMomentum5dPct"], 25.0)
        self.assertAlmostEqual(result[5]["rolloverCostMomentum5dPct"], 0.05)
        self.assertAlmostEqual(result[3]["rolloverCostMomentum3dPct"], 0.03)
        result[6]["nextOi"] = 100000
        result[6]["rolloverCostPct"] = 99.0
        self.assertAlmostEqual(result[5]["nextShareMomentum5d"], 12.5)
        self.assertAlmostEqual(result[5]["rolloverCostMomentum5dPct"], 0.05)


    def test_point_in_time_nifty_trend_uses_only_signal_and_prior_index_sessions(self):
        market = {
            "2026-01-01": 100.0,
            "2026-01-02": 101.0,
            "2026-01-03": 102.0,
            "2026-01-04": 103.0,
            "2026-01-05": 104.0,
            "2026-01-06": 105.0,
            "2026-01-07": 104.0,
        }
        rows = [
            {"symbol": "ABC", "tradeDate": "2026-01-06"},
            {"symbol": "XYZ", "tradeDate": "2026-01-07"},
            {"symbol": "OLD", "tradeDate": "2025-12-31"},
        ]
        result = builder.add_point_in_time_market_momentum(rows, market, horizon=5)
        self.assertAlmostEqual(result[0]["niftyMomentum5dPct"], 5.0)
        self.assertEqual(result[0]["niftyTrend5d"], "UP")
        self.assertAlmostEqual(result[1]["niftyMomentum5dPct"], 104 / 101 * 100 - 100)
        self.assertEqual(result[1]["niftyTrend5d"], "UP")
        self.assertIsNone(result[2]["niftyMomentum5dPct"])
        self.assertEqual(result[2]["niftyTrend5d"], "INSUFFICIENT_HISTORY")

    def test_joint_market_stock_cohorts_require_all_point_in_time_conditions(self):
        base = {
            "rolloverPctFlag": "HIGH", "rolloverCostFlag": "HIGH",
            "nextShareMomentum5d": -1.0, "rolloverCostMomentum5dPct": 0.2,
            "niftyTrend5d": "DOWN", "spotMomentum5dPct": -2.0,
            "totalOiMomentum5dPct": 3.0,
        }
        rows = [
            {**base, "symbol": "MATCH"},
            {**base, "symbol": "WRONG_TREND", "niftyTrend5d": "UP"},
            {**base, "symbol": "WRONG_PRICE", "spotMomentum5dPct": 1.0},
            {**base, "symbol": "WRONG_OI", "totalOiMomentum5dPct": -1.0},
            {**base, "symbol": "MISSING_PRICE", "spotMomentum5dPct": None},
        ]
        cohorts = builder.joint_market_stock_cohorts(rows)
        key = "HIGH_BOTH_SHARE_DOWN_COST_RISING_NIFTY_DOWN_PRICE_DOWN_OI_UP"
        self.assertEqual([row["symbol"] for row in cohorts[key]], ["MATCH"])
        self.assertEqual(len(cohorts), 12)
        up_key = "HIGH_BOTH_SHARE_DOWN_COST_RISING_NIFTY_UP_PRICE_DOWN_OI_UP"
        self.assertEqual([row["symbol"] for row in cohorts[up_key]], ["WRONG_TREND"])

    def test_rising_share_cohorts_are_separate_and_require_all_conditions(self):
        base = {
            "rolloverPctFlag": "HIGH", "rolloverCostFlag": "HIGH",
            "nextShareMomentum5d": 1.0, "rolloverCostMomentum5dPct": 0.2,
            "niftyTrend5d": "DOWN", "spotMomentum5dPct": -2.0,
            "totalOiMomentum5dPct": 3.0,
        }
        rows = [
            {**base, "symbol": "MATCH"},
            {**base, "symbol": "FALLING_SHARE", "nextShareMomentum5d": -1.0},
            {**base, "symbol": "COST_FALLING", "rolloverCostMomentum5dPct": -0.2},
            {**base, "symbol": "OI_DOWN", "totalOiMomentum5dPct": -3.0},
        ]
        cohorts = builder.joint_market_stock_share_increase_cohorts(rows)
        key = "HIGH_BOTH_SHARE_UP_COST_RISING_NIFTY_DOWN_PRICE_DOWN_OI_UP"
        self.assertEqual([row["symbol"] for row in cohorts[key]], ["MATCH"])
        self.assertEqual(len(cohorts), 12)


    def test_rollover_zscore_uses_exactly_63_prior_symbol_sessions_without_lookahead(self):
        rows = [
            {
                "symbol": "ABC",
                "tradeDate": f"2026-01-{index + 1:03d}",
                "rolloverPct": 20.0 + (index % 7),
            }
            for index in range(65)
        ]
        rows[63]["rolloverPct"] = 40.0
        rows[64]["rolloverPct"] = 99.0
        result = builder.add_point_in_time_rollover_zscore(rows, window=63)

        self.assertEqual(result[62]["rolloverZScoreStatus"], "INSUFFICIENT_63_PRIOR_SESSIONS")
        self.assertIsNone(result[62]["rolloverPctZScore63d"])
        self.assertEqual(result[63]["rolloverZScoreStatus"], "AVAILABLE")
        self.assertEqual(result[63]["rolloverPctMean63d"], sum(20.0 + (i % 7) for i in range(63)) / 63)
        self.assertGreater(result[63]["rolloverPctZScore63d"], 0)
        # A later extreme observation must not change the earlier signal's score.
        earlier_score = result[63]["rolloverPctZScore63d"]
        result[64]["rolloverPct"] = 100000.0
        builder.add_point_in_time_rollover_zscore(result, window=63)
        self.assertEqual(result[63]["rolloverPctZScore63d"], earlier_score)

    def test_rollover_zscore_marks_zero_variance_history_unavailable(self):
        rows = [
            {"symbol": "ABC", "tradeDate": f"2026-02-{index + 1:03d}", "rolloverPct": 50.0}
            for index in range(64)
        ]
        result = builder.add_point_in_time_rollover_zscore(rows, window=63)
        self.assertEqual(result[63]["rolloverZScoreStatus"], "ZERO_HISTORICAL_VARIANCE")
        self.assertIsNone(result[63]["rolloverPctZScore63d"])


    def test_cohort_evidence_gate_requires_sample_breadth_and_net_80_percent(self):
        rows = [
            {"symbol": f"S{i % 10}", "signalDate": f"2026-01-{i // 2 + 1:02d}"}
            for i in range(30)
        ]
        summary = {"SHORT_BUILD_UP_20D": {
            "evaluatedSignals": 30, "precisionPct": 83.33,
            "costSensitivity": {"20": {"netPrecisionPct": 80.0}},
        }}
        gate = builder.cohort_evidence_gate(rows, summary)
        self.assertEqual(gate["status"], "BREADTH_OK_NOT_PROOF")
        self.assertTrue(gate["meets80PercentAfter20BpsGate"])
        concentrated = [{"symbol": "ONE", "signalDate": "2026-01-01"} for _ in range(30)]
        blocked = builder.cohort_evidence_gate(concentrated, summary)
        self.assertEqual(blocked["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(blocked["meets80PercentAfter20BpsGate"])
        self.assertIn("SINGLE_SYMBOL_CONCENTRATION_OVER_20_PERCENT", blocked["failedChecks"])


    def test_rollover_zscore_cohorts_are_separate_and_require_high_both_flags(self):
        base = {
            "rolloverPctFlag": "HIGH", "rolloverCostFlag": "HIGH",
            "rolloverZScoreStatus": "AVAILABLE", "rolloverPctZScore63d": 1.8,
        }
        rows = [
            {**base, "symbol": "MATCH_15"},
            {**base, "symbol": "MATCH_20", "rolloverPctZScore63d": 2.2},
            {**base, "symbol": "LOW_Z", "rolloverPctZScore63d": 1.2},
            {**base, "symbol": "NO_HISTORY", "rolloverZScoreStatus": "INSUFFICIENT_63_PRIOR_SESSIONS"},
            {**base, "symbol": "LOW_ROLLOVER", "rolloverPctFlag": "NORMAL"},
            {**base, "symbol": "LOW_COST", "rolloverCostFlag": "NORMAL"},
        ]
        cohorts = builder.joint_rollover_zscore_cohorts(rows)
        self.assertEqual([row["symbol"] for row in cohorts["HIGH_BOTH_ROLLOVER_ZSCORE_15"]], ["MATCH_15", "MATCH_20"])
        self.assertEqual([row["symbol"] for row in cohorts["HIGH_BOTH_ROLLOVER_ZSCORE_20"]], ["MATCH_20"])

        negative_rows = [
            {**base, "symbol": "NEG_QUARTER", "rolloverPctZScore63d": -0.3},
            {**base, "symbol": "NEG_HALF", "rolloverPctZScore63d": -0.7},
            {**base, "symbol": "NEG_ONE", "rolloverPctZScore63d": -1.2},
            {**base, "symbol": "POSITIVE", "rolloverPctZScore63d": 0.1},
            {**base, "symbol": "NO_HISTORY_NEG", "rolloverZScoreStatus": "INSUFFICIENT_63_PRIOR_SESSIONS", "rolloverPctZScore63d": -2.0},
        ]
        negative_cohorts = builder.joint_rollover_zscore_cohorts(negative_rows)
        self.assertEqual([row["symbol"] for row in negative_cohorts["HIGH_BOTH_ROLLOVER_ZSCORE_NEG025"]], ["NEG_QUARTER", "NEG_HALF", "NEG_ONE"])
        self.assertEqual([row["symbol"] for row in negative_cohorts["HIGH_BOTH_ROLLOVER_ZSCORE_NEG05"]], ["NEG_HALF", "NEG_ONE"])
        self.assertEqual([row["symbol"] for row in negative_cohorts["HIGH_BOTH_ROLLOVER_ZSCORE_NEG075"]], ["NEG_ONE"])
        self.assertEqual([row["symbol"] for row in negative_cohorts["HIGH_BOTH_ROLLOVER_ZSCORE_NEG10"]], ["NEG_ONE"])
        self.assertEqual(len(cohorts), 6)


    def test_false_signal_forensics_separates_correct_wrong_and_point_in_time_groups(self):
        base = {
            "rolloverPctFlag": "HIGH", "rolloverCostFlag": "HIGH",
            "nextShareMomentum5d": -1.0, "rolloverCostMomentum5dPct": 0.2,
            "nextBuildUp": "SHORT_BUILD_UP", "niftyTrend5d": "DOWN",
            "spotMomentum5dPct": -1.0, "totalOiMomentum5dPct": 2.0,
            "volatilityRegime": "MEDIUM", "rolloverPct": 75.0,
            "rolloverCostPct": 1.2, "realizedVol20dAnnualizedPct": 28.0,
        }
        rows = [
            {**base, "symbol": "A", "nearOiChange": -10, "nextOiChange": 20, "correct20d": True, "return20dPct": -1.2, "outcome20d": "DOWN"},
            {**base, "symbol": "B", "nearOiChange": 10, "nextOiChange": 20, "correct20d": False, "return20dPct": 0.8, "outcome20d": "UP",
             "niftyTrend5d": "UP", "spotMomentum5dPct": 1.0},
            {**base, "symbol": "C", "nearOiChange": -10, "nextOiChange": -20, "correct20d": None, "return20dPct": 0.1, "outcome20d": "FLAT"},
            {**base, "symbol": "D", "nearOiChange": 10, "nextOiChange": -20, "correct20d": None, "return20dPct": None, "outcome20d": "PENDING"},
            {**base, "symbol": "E", "correct20d": True, "return20dPct": -0.8, "outcome20d": "DOWN",
             "nextBuildUp": "LONG_BUILD_UP"},
            {**base, "symbol": "F", "rolloverPctFlag": "NORMAL",
             "correct20d": False, "return20dPct": 0.9, "outcome20d": "UP"},
        ]
        result = builder.false_signal_forensics(rows)
        self.assertEqual(result["signals"], 4)
        self.assertEqual(result["evaluated"], 2)
        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["wrong"], 1)
        self.assertEqual(result["flatExcluded"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["subgroups"]["niftyTrend5d"]["DOWN"]["evaluated"], 1)
        self.assertEqual(result["subgroups"]["niftyTrend5d"]["UP"]["wrong"], 1)
        self.assertEqual(result["overall"]["netPrecision20BpsPct"], 50.0)
        self.assertEqual(result["overall"]["precisionWilson95Pct"], [9.45, 90.55])
        self.assertEqual(len(result["signalDetails"]), 4)
        self.assertEqual(result["signalDetails"][0]["symbol"], "A")
        self.assertEqual(result["signalDetails"][0]["oiMigrationGroup"], "CONFIRMED_MIGRATION")
        self.assertEqual(result["signalDetails"][0]["nearOiChange"], -10)
        self.assertEqual(result["signalDetails"][0]["nextOiChange"], 20)
        self.assertEqual(result["oiMigrationGroups"]["CONFIRMED_MIGRATION"]["correct"], 1)
        self.assertEqual(result["oiMigrationGroups"]["FRESH_NEXT_EXPIRY_ADDITION"]["wrong"], 1)
        self.assertEqual(result["oiMigrationGroups"]["POSITION_REDUCTION_BOTH"]["signals"], 1)
        self.assertEqual(result["oiMigrationGroups"]["MIXED_OR_UNCONFIRMED"]["signals"], 1)
        self.assertIn("newly accrued prospective", result["interpretationGuard"])
        matched = result["matchedBaselineComparisons"]["niftyTrend5d__stockPriceTrend5d"]
        matched_down_down = next(
            cell for cell in matched["cells"]
            if cell["niftyTrend5d"] == "DOWN" and cell["stockPriceTrend5d"] == "DOWN"
        )
        self.assertEqual(matched_down_down["cohort"]["evaluated"], 1)
        self.assertEqual(matched_down_down["matchedNonCohortShortBaseline"]["evaluated"], 1)
        self.assertEqual(matched_down_down["precisionLiftPercentagePoints"], 100.0)
        self.assertEqual(matched_down_down["warning"], "LOW_SAMPLE_OR_MISSING_COMPARATOR")
        self.assertIn("DEVELOPMENT_ONLY_DIAGNOSTIC", matched["interpretation"])
        interactions = result["pairwiseInteractions"]
        market_stock = interactions["niftyTrend5d__stockPriceTrend5d"]
        self.assertEqual(market_stock["evaluatedSignals"], 2)
        down_down = next(
            cell for cell in market_stock["cells"]
            if cell["left"] == "DOWN" and cell["right"] == "DOWN"
        )
        self.assertEqual(down_down["evaluated"], 1)
        self.assertEqual(down_down["correct"], 1)
        self.assertEqual(down_down["sampleWarning"], "LOW_SAMPLE_LT_5")
        self.assertIn("EXPLORATORY_ONLY", market_stock["interpretation"])
        self.assertIn("DEVELOPMENT_ONLY", market_stock["interpretation"])
        protected_split = builder.false_signal_forensics(
            rows, include_pairwise_interactions=False
        )
        self.assertEqual(protected_split["pairwiseInteractions"], {})
        stricter_threshold = builder.false_signal_forensics([
            {**base, "symbol": "THRESHOLD", "correct20d": True,
             "return20dPct": -0.8, "outcome20d": "DOWN"}
        ], threshold_pct=1.0)
        self.assertEqual(stricter_threshold["overall"]["precisionPct"], 100.0)
        self.assertEqual(stricter_threshold["overall"]["netPrecision20BpsPct"], 0.0)


    def test_cash_delivery_momentum_uses_exact_prior_symbol_session(self):
        rows = [
            {"symbol": "ABC", "tradeDate": f"2026-11-0{day}"}
            for day in range(1, 8)
        ]
        archive = {
            f"2026-11-0{day}": {"ABC": {
                "deliveryPct": value,
                "computedDeliveryPct": value,
                "deliveryPctConsistencyStatus": "MATCH",
            }}
            for day, value in ((1, 20.0), (2, 22.0), (3, 24.0),
                               (4, 26.0), (5, 28.0), (6, 35.0), (7, 40.0))
        }
        result = builder.attach_point_in_time_cash_delivery(rows, archive)
        self.assertEqual(result[5]["deliveryPctMomentum5d"], 15.0)
        self.assertEqual(result[5]["deliveryCoverageStatus"], "AVAILABLE")
        self.assertIsNone(result[4]["deliveryPctMomentum5d"])

    def test_cash_delivery_missing_archive_is_not_zero_filled(self):
        rows = [{"symbol": "ABC", "tradeDate": "2026-11-06"}]
        result = builder.attach_point_in_time_cash_delivery(rows, {})
        self.assertIsNone(result[0]["deliveryPct"])
        self.assertIsNone(result[0]["deliveryPctMomentum5d"])
        self.assertEqual(result[0]["deliveryCoverageStatus"], "DATE_ARCHIVE_MISSING")


    def test_cash_demand_features_use_same_symbol_prior_sessions_and_preserve_missing_data(self):
        rows = [
            {"symbol": "ABC", "tradeDate": f"2026-10-{day:02d}"}
            for day in range(1, 22)
        ]
        archive = {}
        for index, row in enumerate(rows):
            day = row["tradeDate"]
            archive[day] = {"ABC": {
                "deliveryPct": 50.0,
                "computedDeliveryPct": 50.0,
                "deliveryPctConsistencyStatus": "MATCH",
                "deliveryQuantity": 50 + index * 5,
                "tradedQuantity": 100 + index * 10,
                "vwap": 100 + index,
                "closePrice": 102 + index,
            }}
        result = builder.attach_point_in_time_cash_delivery(rows, archive)
        latest = result[-1]
        self.assertEqual(latest["cashDemandCoverageStatus"], "AVAILABLE")
        self.assertAlmostEqual(latest["vwapStrengthPct"], (122 / 120 - 1) * 100)
        self.assertAlmostEqual(latest["deliveryQuantityMomentum5dPct"], (150 / 125 - 1) * 100)
        self.assertAlmostEqual(latest["deliveryQuantityMomentum20dPct"], (150 / 50 - 1) * 100)
        self.assertAlmostEqual(latest["tradedQuantityMomentum20dPct"], (300 / 100 - 1) * 100)
        self.assertAlmostEqual(latest["cashTradedValueProxyMomentum20dPct"], (36000 / 10000 - 1) * 100)

        missing = builder.attach_point_in_time_cash_delivery(
            [{"symbol": "XYZ", "tradeDate": "2026-10-21"}], {}
        )[0]
        self.assertIsNone(missing["deliveryQuantity"])
        self.assertIsNone(missing["cashTradedValueProxy"])
        self.assertIsNone(missing["vwapStrengthPct"])
        self.assertEqual(missing["cashDemandCoverageStatus"], "DATE_ARCHIVE_MISSING")


    def test_delivery_percentage_momentum_excludes_mismatched_source_rows(self):
        metrics = [
            {"symbol": "ABC", "tradeDate": f"2026-01-{day:02d}"}
            for day in range(1, 8)
        ]
        archive = {}
        for day in range(1, 8):
            date = f"2026-01-{day:02d}"
            mismatch = day == 2
            archive[date] = {
                "ABC": {
                    "deliveryPct": 50.0 if mismatch else 40.0 + day,
                    "computedDeliveryPct": 30.0 if mismatch else 40.0 + day,
                    "deliveryPctConsistencyStatus": "MISMATCH" if mismatch else "MATCH",
                    "deliveryQuantity": 100 + day * 10,
                    "tradedQuantity": 200 + day * 10,
                    "vwap": 100.0,
                    "closePrice": 101.0,
                }
            }

        result = builder.attach_point_in_time_cash_delivery(metrics, archive)
        # Day 7 compares to day 2: the mismatched endpoint blocks both
        # delivery-percentage and quantity-derived cash demand momentum.
        self.assertIsNone(result[1]["deliveryPctTrusted"])
        self.assertIsNotNone(result[6]["deliveryPctTrusted"])
        self.assertIsNone(result[6]["deliveryPctMomentum5d"])
        self.assertEqual(
            result[6]["deliveryPctTrendQualityStatus"],
            "PRIOR_SOURCE_MISMATCH_OR_UNVERIFIED",
        )
        self.assertIsNone(result[6]["deliveryQuantityMomentum5dPct"])
        self.assertEqual(result[1]["deliveryPctConsistencyStatus"], "MISMATCH")
        self.assertEqual(result[1]["deliveryPct"], 50.0)
        self.assertEqual(result[1]["computedDeliveryPct"], 30.0)


    def test_unverified_or_mismatched_delivery_rows_do_not_feed_quantity_or_pct_trends(self):
        rows = [
            {"symbol": "ABC", "tradeDate": f"2026-01-{day:02d}"}
            for day in range(1, 8)
        ]
        archive = {}
        for day in range(1, 8):
            status = "MISMATCH" if day == 2 else "MATCH"
            archive[f"2026-01-{day:02d}"] = {"ABC": {
                "deliveryPct": 55.0 if day == 2 else 50.0,
                "computedDeliveryPct": 30.0 if day == 2 else 50.0,
                "deliveryPctConsistencyStatus": status,
                "deliveryQuantity": 100 + day * 10,
                "tradedQuantity": 200 + day * 10,
                "vwap": 100.0,
                "closePrice": 101.0,
            }}
        result = builder.attach_point_in_time_cash_delivery(rows, archive)
        self.assertIsNone(result[1]["deliveryPctTrusted"])
        self.assertIsNone(result[1]["deliveryQuantity"])
        self.assertIsNone(result[1]["tradedQuantity"])
        self.assertIsNone(result[1]["cashTradedValueProxy"])
        self.assertIsNone(result[6]["deliveryPctMomentum5d"])
        self.assertIsNone(result[6]["deliveryQuantityMomentum5dPct"])
        self.assertIsNone(result[6]["tradedQuantityMomentum5dPct"])
        self.assertIsNone(result[6]["cashTradedValueProxyMomentum5dPct"])
        self.assertIsNotNone(result[6]["vwapStrengthPct"])

    def test_delivery_day_quarantine_threshold_and_minimum_comparisons(self):
        below_minimum = {
            f"S{i}": {
                "deliveryPct": 60.0 if i < 10 else 50.0,
                "computedDeliveryPct": 30.0 if i < 10 else 50.0,
            }
            for i in range(99)
        }
        self.assertEqual(
            builder.cash_delivery_day_quality(below_minimum)["status"],
            "USABLE",
        )

        at_threshold = {
            f"S{i}": {
                "deliveryPct": 60.0 if i < 10 else 50.0,
                "computedDeliveryPct": 30.0 if i < 10 else 50.0,
            }
            for i in range(100)
        }
        quality = builder.cash_delivery_day_quality(at_threshold)
        self.assertEqual(quality["status"], "QUARANTINED_SYSTEMIC_MISMATCH")
        self.assertEqual(quality["comparableRows"], 100)
        self.assertAlmostEqual(quality["mismatchRate"], 0.10)

    def test_systemically_inconsistent_delivery_date_is_quarantined(self):
        daily = {}
        for index in range(100):
            symbol = f"STOCK{index}"
            mismatch = index < 20
            daily[symbol] = {
                "deliveryPct": 60.0 if mismatch else 50.0,
                "computedDeliveryPct": 30.0 if mismatch else 50.0,
                "deliveryQuantity": 600,
                "tradedQuantity": 1000,
                "vwap": 100.0,
                "closePrice": 101.0,
            }
        metrics = [{"symbol": "STOCK99", "tradeDate": "2026-09-11"}]
        result = builder.attach_point_in_time_cash_delivery(
            metrics, {"2026-09-11": daily}
        )[0]
        self.assertEqual(
            result["cashDeliveryDayQualityStatus"],
            "QUARANTINED_SYSTEMIC_MISMATCH",
        )
        self.assertEqual(
            result["deliveryCoverageStatus"],
            "DATE_DATA_QUALITY_QUARANTINED",
        )
        self.assertIsNone(result["deliveryPctTrusted"])
        self.assertIsNone(result["deliveryQuantity"])
        self.assertIsNone(result["cashVwap"])

    def test_legacy_delivery_rows_rederive_consistency_from_archived_percentages(self):
        rows = [{"symbol": "ABC", "tradeDate": f"2026-01-{day:02d}"} for day in range(1, 8)]
        archive = {}
        for day in range(1, 8):
            mismatch = day == 2
            archive[f"2026-01-{day:02d}"] = {"ABC": {
                "deliveryPct": 55.0 if mismatch else 50.0,
                "computedDeliveryPct": 30.0 if mismatch else 50.0,
                "deliveryQuantity": 100 + day,
                "tradedQuantity": 200 + day,
                "vwap": 100.0,
                "closePrice": 101.0,
            }}
        result = builder.attach_point_in_time_cash_delivery(rows, archive)
        self.assertEqual(result[0]["deliveryPctConsistencyStatus"], "MATCH")
        self.assertEqual(result[0]["deliveryPctTrusted"], 50.0)
        self.assertEqual(result[1]["deliveryPctConsistencyStatus"], "MISMATCH")
        self.assertIsNone(result[1]["deliveryPctTrusted"])
        self.assertIsNone(result[1]["deliveryQuantity"])
        self.assertIsNone(result[6]["deliveryPctMomentum5d"])
        self.assertIsNone(result[6]["deliveryQuantityMomentum5dPct"])

    def test_legacy_delivery_rows_without_consistency_status_are_unverified(self):
        rows = [{"symbol": "ABC", "tradeDate": f"2026-01-{day:02d}"} for day in range(1, 8)]
        archive = {
            f"2026-01-{day:02d}": {"ABC": {
                "deliveryPct": 50.0,
                "deliveryQuantity": 100 + day,
                "tradedQuantity": 200 + day,
                "vwap": 100.0,
                "closePrice": 101.0,
            }}
            for day in range(1, 8)
        }
        result = builder.attach_point_in_time_cash_delivery(rows, archive)
        self.assertEqual(result[-1]["deliveryPctConsistencyStatus"], "UNVERIFIED")
        self.assertIsNone(result[-1]["deliveryPctTrusted"])
        self.assertIsNone(result[-1]["deliveryQuantity"])
        self.assertIsNone(result[-1]["tradedQuantity"])
        self.assertIsNone(result[-1]["deliveryPctMomentum5d"])
        self.assertIsNone(result[-1]["deliveryQuantityMomentum5dPct"])



if __name__ == "__main__":
    unittest.main()
