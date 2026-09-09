from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h7.pipeline import run_h7, validate_contract, validate_ddl


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path) -> dict[str, object]:
    return run_h7(
        contract_path=ROOT / "contracts/h7-b0-overwrite.json",
        ddl_path=ROOT / "infra/spark/h7-b0.sql",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        operations_output=output / "operations.csv",
        state_output=output / "state.csv",
        reproducibility_output=output / "reproducibility.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


class H7B0OverwriteTests(unittest.TestCase):
    def test_h7_is_deterministic_and_exposes_overwrite_cost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["input_rows"], 38)
            self.assertEqual(first["vintage_batches"], 3)
            self.assertEqual(first["final_rows"], 14)
            self.assertEqual(first["overwritten_rows"], 24)
            self.assertEqual(first["value_changed_rows"], 14)
            self.assertEqual(first["same_value_overwrites"], 10)
            self.assertEqual(first["reproduction_successes"], 14)
            self.assertEqual(first["reproduction_failures"], 24)

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workload"]["vintage_read_success_rate"], "0.3684")
            self.assertFalse(
                manifest["reproducibility"]["historical_reproduction_capable"]
            )

    def test_final_state_keeps_only_the_latest_observation_per_cell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "state.csv").open(newline="", encoding="utf-8") as handle:
                state = list(csv.DictReader(handle))
            with (output / "reproducibility.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                reads = list(csv.DictReader(handle))

            self.assertEqual(len(state), 14)
            self.assertEqual(len({row["cell_id"] for row in state}), 14)
            current = {row["cell_id"]: row for row in state}
            self.assertEqual(sum(row["result"] == "current_available" for row in reads), 14)
            self.assertEqual(
                sum(row["result"] == "historical_overwritten" for row in reads), 24
            )
            for row in reads:
                available = row["result"] == "current_available"
                self.assertEqual(
                    available,
                    row["requested_observation_id"]
                    == current[row["cell_id"]]["observation_id"],
                )

    def test_contract_rejects_retained_history(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h7-b0-overwrite.json").read_text(encoding="utf-8")
        )
        contract["state"]["history_policy"] = "retain Iceberg snapshots"
        with self.assertRaisesRegex(ValueError, "must not retain"):
            validate_contract(contract)

    def test_ddl_matches_contract_and_h6_schema(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h7-b0-overwrite.json").read_text(encoding="utf-8")
        )
        ddl = (ROOT / "infra/spark/h7-b0.sql").read_text(encoding="utf-8")
        validate_ddl(contract, ddl)
        with self.assertRaisesRegex(ValueError, "value_decimal"):
            validate_ddl(contract, ddl.replace("value_decimal DECIMAL(38,10)", "value_decimal DOUBLE"))


if __name__ == "__main__":
    unittest.main()
