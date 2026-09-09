from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h7b.pipeline import run_h7b, validate_contract, validate_ddl


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path) -> dict[str, object]:
    return run_h7b(
        contract_path=ROOT / "contracts/h7b-b2-single-source.json",
        ddl_path=ROOT / "infra/spark/h7b-b2.sql",
        h6b_manifest_path=ROOT / "data/manifests/h6b-source-trust.json",
        state_output=output / "state.csv",
        discarded_output=output / "discarded.csv",
        reproducibility_output=output / "reproducibility.csv",
        summary_output=output / "summary.csv",
        validation_output=output / "validation.csv",
        manifest_output=output / "manifest.json",
    )


class H7BSingleSourceTests(unittest.TestCase):
    def test_h7b_is_deterministic_and_materializes_b2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["input_rows"], 38)
            self.assertEqual(first["selected_rows"], 14)
            self.assertEqual(first["discarded_rows"], 24)
            self.assertEqual(first["lower_score_discards"], 10)
            self.assertEqual(first["tie_break_discards"], 14)
            self.assertEqual(first["latest_selected"], 4)
            self.assertEqual(first["older_selected"], 10)
            self.assertEqual(first["value_differs_from_latest"], 10)
            self.assertEqual(first["reproduction_successes"], 14)
            self.assertEqual(first["reproduction_failures"], 24)

    def test_selected_and_discarded_rows_partition_the_h6_workload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "state.csv").open(newline="", encoding="utf-8") as handle:
                state = list(csv.DictReader(handle))
            with (output / "discarded.csv").open(newline="", encoding="utf-8") as handle:
                discarded = list(csv.DictReader(handle))
            with (output / "reproducibility.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                reads = list(csv.DictReader(handle))

            selected_ids = {row["observation_id"] for row in state}
            discarded_ids = {row["discarded_observation_id"] for row in discarded}
            self.assertFalse(selected_ids & discarded_ids)
            self.assertEqual(len(selected_ids | discarded_ids), 38)
            self.assertEqual({row["selected_source_id"] for row in state}, {"bps_tpb_2025"})
            self.assertEqual(len({row["cell_id"] for row in state}), 14)
            for row in reads:
                self.assertEqual(
                    row["available_by_observation_id"] == "yes",
                    row["requested_observation_id"] in selected_ids,
                )

    def test_contract_rejects_post_conflict_rescoring(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h7b-b2-single-source.json").read_text(encoding="utf-8")
        )
        contract["input"]["selection_policy"] = "rescore after comparing values"
        with self.assertRaisesRegex(ValueError, "must not rescore"):
            validate_contract(contract)

    def test_ddl_matches_contract_and_h6_schema(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h7b-b2-single-source.json").read_text(encoding="utf-8")
        )
        ddl = (ROOT / "infra/spark/h7b-b2.sql").read_text(encoding="utf-8")
        validate_ddl(contract, ddl)
        with self.assertRaisesRegex(ValueError, "trust_score"):
            validate_ddl(contract, ddl.replace("trust_score DECIMAL(7,6)", "trust_score DOUBLE"))


if __name__ == "__main__":
    unittest.main()
