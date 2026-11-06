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

if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
