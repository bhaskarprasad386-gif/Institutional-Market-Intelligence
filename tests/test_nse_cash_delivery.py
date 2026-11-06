import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "nse"))
import fetch_cash_delivery as delivery


class CashDeliveryParserTests(unittest.TestCase):
    def test_parses_eq_delivery_and_calculates_percentage(self):
        csv_text = (
            "SYMBOL,SERIES,DATE1,CLOSE_PRICE,AVG_PRICE,TTL_TRD_QNTY,"
            "DELIV_QTY,DELIV_PER,NO_OF_TRADES\n"
            "ABC,EQ,05-Nov-2026,100,99.5,10000,4200,42.00,500\n"
            "ABC,BE,05-Nov-2026,100,99.5,10000,4200,42.00,500\n"
        )
        rows = delivery.parse_cash_delivery_csv(csv_text, dt.date(2026, 11, 5))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "ABC")
        self.assertEqual(rows[0]["deliveryQuantity"], 4200)
        self.assertEqual(rows[0]["deliveryPct"], 42.0)
        self.assertEqual(rows[0]["computedDeliveryPct"], 42.0)

    def test_rejects_delivery_greater_than_traded_quantity(self):
        csv_text = (
            "SYMBOL,SERIES,DATE1,CLOSE_PRICE,AVG_PRICE,TTL_TRD_QNTY,"
            "DELIV_QTY,DELIV_PER,NO_OF_TRADES\n"
            "ABC,EQ,05-Nov-2026,100,99.5,10000,11000,110,500\n"
        )
        with self.assertRaisesRegex(ValueError, "quantities"):
            delivery.parse_cash_delivery_csv(csv_text, dt.date(2026, 11, 5))

    def test_rejects_mismatched_delivery_percentage(self):
        csv_text = (
            "SYMBOL,SERIES,DATE1,CLOSE_PRICE,AVG_PRICE,TTL_TRD_QNTY,"
            "DELIV_QTY,DELIV_PER,NO_OF_TRADES\n"
            "ABC,EQ,05-Nov-2026,100,99.5,10000,4200,20,500\n"
        )
        with self.assertRaisesRegex(ValueError, "disagree"):
            delivery.parse_cash_delivery_csv(csv_text, dt.date(2026, 11, 5))

    def test_rejects_wrong_date_and_missing_eq_rows(self):
        csv_text = (
            "SYMBOL,SERIES,DATE1,CLOSE_PRICE,AVG_PRICE,TTL_TRD_QNTY,"
            "DELIV_QTY,DELIV_PER,NO_OF_TRADES\n"
            "ABC,EQ,04-Nov-2026,100,99.5,10000,4200,42,500\n"
        )
        with self.assertRaisesRegex(ValueError, "No valid EQ"):
            delivery.parse_cash_delivery_csv(csv_text, dt.date(2026, 11, 5))

    def test_partial_backfill_is_reported_as_failure(self):
        with self.assertRaisesRegex(SystemExit, "backfill incomplete: 2 dates failed"):
            delivery.ensure_backfill_complete(10, 3, 2)

    def test_complete_backfill_passes(self):
        self.assertIsNone(delivery.ensure_backfill_complete(10, 5, 0))

    def test_already_archived_backfill_passes(self):
        self.assertIsNone(delivery.ensure_backfill_complete(0, 603, 0))


if __name__ == "__main__":
    unittest.main()
