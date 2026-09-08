from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h1.compare import compare_files
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


if __name__ == "__main__":
    unittest.main()
