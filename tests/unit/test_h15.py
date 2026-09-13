from __future__ import annotations

import csv
import json
import os
import unittest
from pathlib import Path

from kkciv_vintage.h15.pipeline import build_inventories, validate_contract


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("contracts/h15-result-tables-and-figures.json")
PROCESSED = Path("results/processed")
DRAFT = Path("papers/vintage_reconciliation/draft/05-hasil.md")
KEY_NUMBERS = Path("papers/vintage_reconciliation/data/angka-kunci.csv")


def setUpModule() -> None:
    os.chdir(ROOT)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class ContractTest(unittest.TestCase):
    def test_frozen_contract_is_accepted(self) -> None:
        validate_contract(_contract())

    def test_the_frame_frozen_at_h11_is_not_negotiable(self) -> None:
        contract = _contract()
        contract["frozen_frame"]["tables"] = 20
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_hand_typed_values_are_forbidden(self) -> None:
        contract = _contract()
        contract["sources"]["no_manual_numbers"] = "values may be typed in when convenient"
        with self.assertRaises(ValueError):
            validate_contract(contract)


class InventoryTest(unittest.TestCase):
    def test_a_table_added_after_the_frame_must_carry_its_reason(self) -> None:
        contract = _contract()
        composed = {
            "T7": {
                "rq": "P3",
                "title": "frame table",
                "rows": 4,
                "path": "results/processed/h15-table-t7.csv",
                "sources": ["h11-sweep-scenarios.csv"],
                "origin": "frozen_frame",
                "note": "",
            },
            "T15": {
                "rq": "P3",
                "title": "added table",
                "rows": 4,
                "path": "results/processed/h15-table-t15.csv",
                "sources": ["h12-arrival-cost.csv"],
                "origin": "added_after_the_frame_was_frozen",
                "note": "",
            },
        }
        tables, _ = build_inventories(contract=contract, composed=composed, figures=[])
        added = [row for row in tables if row["origin"].startswith("added")]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["note"], "")

    def test_every_caption_carries_the_environment_note(self) -> None:
        contract = _contract()
        _, figures = build_inventories(contract=contract, composed={}, figures=[])
        self.assertEqual(len(figures), 4)
        for row in figures:
            self.assertIn(contract["environment_note"], row["caption"])


class CommittedOutputTest(unittest.TestCase):
    def test_the_committed_tables_match_their_inventory(self) -> None:
        inventory = _read_csv(PROCESSED / "h15-table-inventory.csv")
        self.assertTrue(inventory)
        for row in inventory:
            path = Path(row["output_path"])
            self.assertTrue(path.exists(), row["output_path"])
            self.assertEqual(len(_read_csv(path)), int(row["rows"]), row["table_id"])
            self.assertTrue(row["sources"], row["table_id"])

    def test_the_sweep_tables_cover_the_six_frozen_points(self) -> None:
        for name in ("h15-table-t8.csv", "h15-table-t9.csv"):
            rows = _read_csv(PROCESSED / name)
            self.assertEqual(
                [row["cells_revised"] for row in rows], ["1", "2", "4", "8", "16", "38"], name
            )

    def test_figure_points_carry_a_range_where_repetitions_exist(self) -> None:
        rows = _read_csv(PROCESSED / "h15-figure-data.csv")
        for row in rows:
            if row["figure_id"] in {"G1", "G2"}:
                self.assertTrue(row["y_min"] and row["y_max"], row)
                self.assertLessEqual(float(row["y_min"]), float(row["y"]) + 1e-6)
                self.assertGreaterEqual(float(row["y_max"]), float(row["y"]) - 1e-6)


class DraftTest(unittest.TestCase):
    def test_every_metric_id_the_draft_cites_exists(self) -> None:
        import re

        numbers = {row["metric_id"] for row in _read_csv(KEY_NUMBERS)}
        cited = set(re.findall(r"`((?:p\d|s2|b2)_[a-z0-9_]+)`", DRAFT.read_text(encoding="utf-8")))
        self.assertTrue(cited)
        self.assertEqual(cited - numbers, set())

    def test_the_draft_states_the_environment_limit(self) -> None:
        text = DRAFT.read_text(encoding="utf-8")
        self.assertIn("2 vCPU", text)
        self.assertIn("perbandingan", text)


if __name__ == "__main__":
    unittest.main()
