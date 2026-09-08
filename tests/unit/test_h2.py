from __future__ import annotations

import unittest

from kkciv_vintage.h2.pipeline import _record_key, extract_webapi_series


class H2ExtractionTests(unittest.TestCase):
    def test_record_key_matches_bps_composite_key(self) -> None:
        self.assertEqual(
            _record_key(
                geography_id="9999",
                variable_id="1980",
                category_id="1672",
                period_id="123",
                derived_period_id="0",
            ),
            "9999198016721230",
        )

    def test_extracts_only_selected_national_annual_series(self) -> None:
        payload = {
            "request": {"domain": "0000"},
            "responses": [
                {
                    "var": [{"val": 1980}],
                    "vervar": [
                        {"val": 1100, "label": "ACEH"},
                        {"val": 9999, "label": "INDONESIA"},
                    ],
                    "turvar": [
                        {"val": 1672, "label": "SD"},
                        {"val": 1673, "label": "SMP"},
                    ],
                    "tahun": [
                        {"val": 122, "label": "2022"},
                        {"val": 123, "label": "2023"},
                    ],
                    "turtahun": [{"val": 0, "label": "Tahun"}],
                    "datacontent": {
                        "9999198016721220": 97.82,
                        "9999198016721230": 97.83,
                        "9999198016731230": 90.44,
                        "1100198016721230": 99.08,
                    },
                    "last_update": "2026-08-26 08:29:01",
                }
            ],
        }
        rows = extract_webapi_series(
            payload=payload,
            indicator_key="sdg04_completion_rate",
            series_key="sd",
            category_id="1672",
            unit="percent",
            producer="Badan Pusat Statistik",
            release_date="2026-09-08",
            selected_years={"2022", "2023"},
        )
        self.assertEqual([row["value"] for row in rows], ["97.82", "97.83"])
        self.assertTrue(all(row["geo_code"] == "9999" for row in rows))
        self.assertTrue(all(row["series_key"] == "sd" for row in rows))


if __name__ == "__main__":
    unittest.main()
