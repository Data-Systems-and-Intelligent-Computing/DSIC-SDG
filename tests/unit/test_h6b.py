from __future__ import annotations

import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from kkciv_vintage.h6b.pipeline import run_h6b, validate_contract


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path) -> dict[str, object]:
    return run_h6b(
        contract_path=ROOT / "contracts/h6b-source-trust.json",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        source_registry_path=ROOT / "config/sources/bps_sources.csv",
        scores_output=output / "scores.csv",
        selection_output=output / "selection.csv",
        validation_output=output / "validation.csv",
        manifest_output=output / "manifest.json",
    )


class H6BSourceTrustTests(unittest.TestCase):
    def test_score_is_deterministic_and_frozen_on_the_h6_workload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["source_count"], 3)
            self.assertEqual(first["cell_count"], 14)
            self.assertEqual(first["latest_selected"], 4)
            self.assertEqual(first["older_selected"], 10)
            self.assertEqual(first["selected_value_differs"], 10)

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["score_status"], "frozen")
            self.assertTrue(manifest["selection_preview"]["diagnostic_only"])

    def test_weighted_scores_and_tie_break_match_the_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "scores.csv").open(newline="", encoding="utf-8") as handle:
                scores = list(csv.DictReader(handle))
            with (output / "selection.csv").open(newline="", encoding="utf-8") as handle:
                selection = list(csv.DictReader(handle))

            self.assertEqual(
                [row["source_id"] for row in scores],
                ["bps_tpb_2025", "bps_tpb_2024", "bps_webapi"],
            )
            self.assertEqual(Decimal(scores[0]["trust_score"]), Decimal("0.962500"))
            self.assertEqual(Decimal(scores[1]["trust_score"]), Decimal("0.962500"))
            self.assertEqual(Decimal(scores[2]["trust_score"]), Decimal("0.907143"))
            self.assertEqual({row["selected_source_id"] for row in selection}, {"bps_tpb_2025"})
            self.assertEqual(sum(row["candidate_count"] == "3" for row in selection), 10)
            self.assertEqual(sum(row["candidate_count"] == "2" for row in selection), 4)

    def test_contract_rejects_outcome_leakage(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h6b-source-trust.json").read_text(encoding="utf-8")
        )
        contract["forbidden_score_features"].remove("value_decimal")
        with self.assertRaisesRegex(ValueError, "outcome-leaking"):
            validate_contract(contract)

    def test_contract_rejects_weights_that_do_not_sum_to_one(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h6b-source-trust.json").read_text(encoding="utf-8")
        )
        contract["dimensions"][0]["weight"] = "0.31"
        with self.assertRaisesRegex(ValueError, "sum to one"):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
