from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h1.compare import compare_files
from kkciv_vintage.h1.coverage import _classify_vervar, _derive_status, _profile_variable
from kkciv_vintage.h1.inventory import validate_inventory


ROOT = Path(__file__).resolve().parents[2]


class InventoryTests(unittest.TestCase):
    def test_committed_inventory_is_valid(self) -> None:
        errors = validate_inventory(
            ROOT / "config/sources/bps_sources.csv",
            ROOT / "config/indicators",
        )
        self.assertEqual(errors, [])


class ComparisonTests(unittest.TestCase):
    def test_example_detects_match_and_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.csv"
            rows = compare_files(
                [
                    ROOT / "examples/h1/source_webapi.csv",
                    ROOT / "examples/h1/source_tpb_publication.csv",
                ],
                output,
            )
            self.assertEqual({row["status"] for row in rows}, {"exact_match", "value_mismatch"})
            with output.open(newline="", encoding="utf-8") as handle:
                written = list(csv.DictReader(handle))
            self.assertEqual(len(written), 2)


class CoverageTests(unittest.TestCase):
    def test_vervar_codes_map_to_geography_levels(self) -> None:
        self.assertEqual(_classify_vervar(9999), "national")
        self.assertEqual(_classify_vervar(1100), "province")
        self.assertEqual(_classify_vervar(1101), "regency")
        self.assertEqual(_classify_vervar(3), "non_spatial")

    def test_profile_counts_cells_years_and_missingness(self) -> None:
        payload = {
            "responses": [
                {
                    "datacontent": {"1100999920011230": 1.0, "9999999920011230": 2.0},
                    "vervar": [{"val": 1100, "label": "ACEH"}, {"val": 9999, "label": "INDONESIA"}],
                    "turvar": [{"val": 2001, "label": "SD"}, {"val": 2002, "label": "SMP"}],
                    "tahun": [{"val": 123, "label": "2023"}, {"val": 125, "label": "2025"}],
                    "turtahun": [{"val": 0, "label": "Tahun"}],
                    "var": [{"val": 9999, "label": "Contoh"}],
                    "subject": [{"val": 1, "label": "Pendidikan"}],
                    "last_update": "2026-01-02 03:04:05",
                    "labelvervar": "38 Provinsi",
                }
            ]
        }
        profile = _profile_variable(payload)
        self.assertEqual(profile["geography_levels"], ["national", "province"])
        self.assertEqual(profile["years"], [2023, 2025])
        self.assertEqual(profile["period_gaps"], [2024])
        self.assertEqual(profile["observed_cells"], 2)
        self.assertEqual(profile["expected_cells"], 8)
        self.assertEqual(profile["title"], "Contoh")

    def test_non_spatial_unit_dimension_is_reported_as_national(self) -> None:
        payload = {
            "responses": [
                {
                    "datacontent": {"1179420001150": 1.0},
                    "vervar": [{"val": 1, "label": "SD"}, {"val": 2, "label": "SMP"}],
                    "turvar": [],
                    "tahun": [{"val": 115, "label": "2015"}],
                    "turtahun": [{"val": 0, "label": "Tahun"}],
                    "var": [{"val": 1794, "label": "Akses Listrik"}],
                    "subject": [],
                    "last_update": "2024-04-22 09:22:05",
                    "labelvervar": "Tingkat Sekolah",
                }
            ]
        }
        profile = _profile_variable(payload)
        self.assertEqual(profile["geography_levels"], ["national"])
        self.assertEqual(profile["category_dimensions"], ["Tingkat Sekolah"])

    def test_status_rules_follow_confirmed_free_source_coverage(self) -> None:
        full = dict(proposed_geographies=["national"], verified_geographies=["national"])
        self.assertEqual(
            _derive_status(evidence_sources={"bps_webapi"}, **full)[0],
            "verified",
        )
        self.assertEqual(
            _derive_status(
                evidence_sources={"bps_webapi", "bps_tpb_2024"}, **full
            )[0],
            "verified",
        )
        self.assertEqual(
            _derive_status(
                evidence_sources={"bps_webapi"},
                proposed_geographies=["national", "regency"],
                verified_geographies=["national"],
            )[0],
            "partial",
        )
        self.assertEqual(
            _derive_status(evidence_sources=set(), **full)[0],
            "unavailable",
        )

    def test_no_geography_flag_without_observations(self) -> None:
        _, _, flags = _derive_status(
            proposed_geographies=["national", "province"],
            verified_geographies=[],
            evidence_sources=set(),
        )
        self.assertEqual(flags, [])


if __name__ == "__main__":
    unittest.main()
