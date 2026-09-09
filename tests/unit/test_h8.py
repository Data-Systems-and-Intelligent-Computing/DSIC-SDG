from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h8.pipeline import run_h8, validate_contract, validate_ddl


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path) -> dict[str, object]:
    return run_h8(
        contract_path=ROOT / "contracts/h8-b1-full-snapshot.json",
        ddl_path=ROOT / "infra/spark/h8-b1.sql",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        b0_manifest_path=ROOT / "data/manifests/h7-b0-overwrite.json",
        catalog_output=output / "catalog.csv",
        snapshot_states_output=output / "snapshot-states.csv",
        current_state_output=output / "current-state.csv",
        reproducibility_output=output / "reproducibility.csv",
        validation_output=output / "validation.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


class H8B1FullSnapshotTests(unittest.TestCase):
    def test_h8_is_deterministic_and_materializes_complete_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["input_rows"], 38)
            self.assertEqual(first["snapshot_count"], 3)
            self.assertEqual(first["final_rows"], 14)
            self.assertEqual(first["logical_full_copy_rows"], 42)
            self.assertEqual(first["distinct_observations_stored"], 38)
            self.assertEqual(first["carried_forward_row_appearances"], 4)
            self.assertEqual(first["reproduction_successes"], 38)
            self.assertEqual(first["reproduction_failures"], 0)

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workload"]["vintage_read_success_rate"], "1.0000")
            self.assertTrue(manifest["reproducibility"]["historical_reproduction_capable"])
            self.assertEqual(
                manifest["measurement"]["physical_bytes_and_runtime"], "deferred_to_H10"
            )

    def test_every_release_is_complete_and_every_observation_is_recallable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "snapshot-states.csv").open(newline="", encoding="utf-8") as handle:
                states = list(csv.DictReader(handle))
            with (output / "reproducibility.csv").open(newline="", encoding="utf-8") as handle:
                reads = list(csv.DictReader(handle))

            for order in ("1", "2", "3"):
                release = [row for row in states if row["snapshot_order"] == order]
                self.assertEqual(len(release), 14)
                self.assertEqual(len({row["cell_id"] for row in release}), 14)
            self.assertEqual(len(reads), 38)
            self.assertTrue(all(row["available_by_snapshot"] == "yes" for row in reads))
            self.assertEqual(
                sum(row["result"] == "historical_snapshot_available" for row in reads), 24
            )
            self.assertEqual(
                sum(row["result"] == "current_snapshot_available" for row in reads), 14
            )

    def test_contract_rejects_snapshot_expiration(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h8-b1-full-snapshot.json").read_text(encoding="utf-8")
        )
        contract["state"]["history_policy"] = "expire old snapshots"
        with self.assertRaisesRegex(ValueError, "must retain"):
            validate_contract(contract)

    def test_ddl_matches_contract_and_forbids_expiration(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h8-b1-full-snapshot.json").read_text(encoding="utf-8")
        )
        ddl = (ROOT / "infra/spark/h8-b1.sql").read_text(encoding="utf-8")
        validate_ddl(contract, ddl)
        with self.assertRaisesRegex(ValueError, "expire"):
            validate_ddl(contract, ddl + "\nCALL kkciv.system.expire_snapshots();")
        with self.assertRaisesRegex(ValueError, "value_decimal"):
            validate_ddl(
                contract, ddl.replace("value_decimal DECIMAL(38,10)", "value_decimal DOUBLE")
            )


if __name__ == "__main__":
    unittest.main()
