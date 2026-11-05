import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.nse import build_rollover_history as builder


class RolloverHistoryBuilderTests(unittest.TestCase):
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
            self.assertTrue((root / "rollover-metrics.json").exists())

if __name__ == "__main__":
    unittest.main()
