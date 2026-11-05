import csv
import datetime as dt
import io
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "nse"))
import backfill_fo_history as backfill


class BackfillParserTests(unittest.TestCase):
    def test_cli_date_parser_trims_surrounding_whitespace(self):
        self.assertEqual(backfill.parse_cli_date(" 2024-07-07 ", "end-date"), dt.date(2024, 7, 7))
        self.assertEqual(backfill.parse_cli_date("2024-06-08\\n", "start-date"), dt.date(2024, 6, 8))

    def test_cli_date_parser_rejects_invalid_or_non_iso_dates(self):
        for raw in ("", "2024/07/07", "2024-02-30"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    backfill.parse_cli_date(raw, "end-date")

    def test_parse_day_supports_legacy_date_formats(self):
        self.assertEqual(backfill.parse_day("04-NOV-2026"), "2026-11-04")
        self.assertEqual(backfill.parse_day("2026-11-04"), "2026-11-04")
        self.assertEqual(backfill.parse_day("not-a-date"), "")

    def test_legacy_zip_parser_maps_only_futures_rows(self):
        day = dt.date(2024, 6, 27)
        csv_text = (
            "INSTRUMENT,TIMESTAMP,EXPIRY_DT,SYMBOL,SETTLE_PR,OPEN_INT,CONTRACTS\n"
            "FUTIDX,27-JUN-2024,25-JUL-2024,NIFTY,24000.5,123456,1000\n"
            "OPTIDX,27-JUN-2024,25-JUL-2024,NIFTY,100.0,999,50\n"
        )
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("fo.csv", csv_text)
        with patch.object(backfill.urllib.request, "urlopen", return_value=io.BytesIO(payload.getvalue())):
            filename, rows = backfill.fetch_legacy(day)

        self.assertEqual(filename, "fo27JUN2024bhav.csv.zip")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "NIFTY")
        self.assertEqual(rows[0]["tradeDate"], "2024-06-27")
        self.assertEqual(rows[0]["spotClose"], "0")
        self.assertEqual(rows[0]["openInterest"], "123456")

    def test_validate_rows_accepts_zero_oi_and_missing_spot_placeholder(self):
        day = dt.date(2024, 6, 27)
        rows = [{
            "tradeDate": day.isoformat(), "expiryDate": "2024-07-25",
            "futuresClose": "24000.5", "openInterest": "0", "spotClose": "0",
        }]
        backfill.validate_rows(day, rows)

    def test_validate_rows_rejects_non_finite_values(self):
        day = dt.date(2024, 6, 27)
        for field, bad_value in (("futuresClose", "NaN"), ("futuresClose", "Infinity"),
                                 ("openInterest", "NaN"), ("openInterest", "Infinity")):
            with self.subTest(field=field, value=bad_value):
                rows = [{
                    "tradeDate": day.isoformat(), "expiryDate": "2024-07-25",
                    "futuresClose": "24000", "openInterest": "100",
                }]
                rows[0][field] = bad_value
                with self.assertRaisesRegex(ValueError, "finite"):
                    backfill.validate_rows(day, rows)

    def test_validate_rows_rejects_invalid_prices_oi_and_expiry(self):
        day = dt.date(2024, 6, 27)
        cases = [
            {"futuresClose": "0", "openInterest": "10", "expiryDate": "2024-07-25"},
            {"futuresClose": "10", "openInterest": "-1", "expiryDate": "2024-07-25"},
            {"futuresClose": "10", "openInterest": "1", "expiryDate": "2024-06-26"},
        ]
        for values in cases:
            with self.subTest(values=values):
                rows = [{"tradeDate": day.isoformat(), **values}]
                with self.assertRaises(ValueError):
                    backfill.validate_rows(day, rows)


if __name__ == "__main__":
    unittest.main()
