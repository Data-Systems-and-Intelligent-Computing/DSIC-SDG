from __future__ import annotations

import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from kkciv_vintage.h8b.pipeline import run_h8b, validate_contract, validate_human_decisions


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path) -> dict[str, object]:
    return run_h8b(
        contract_path=ROOT / "contracts/h8b-injected-revision-harness.json",
        scenario_path=ROOT / "config/h8b/injection_scenarios.csv",
        human_decisions_path=ROOT / "config/h8b/human_decisions.csv",
        b0_manifest_path=ROOT / "data/manifests/h7-b0-overwrite.json",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        plan_output=output / "plan.csv",
        injections_output=output / "injections.csv",
        routes_output=output / "routes.csv",
        validation_output=output / "validation.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


class H8BInjectedRevisionHarnessTests(unittest.TestCase):
    def test_harness_is_deterministic_and_validation_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["base_cells"], 14)
            self.assertEqual(first["scenario_count"], 5)
            self.assertEqual(first["scenario_sizes"], "1-2-4-7-14")
            self.assertEqual(first["injected_rows"], 28)
            self.assertEqual(first["route_rows"], 20)
            self.assertEqual(first["route_mismatches"], 0)
            self.assertEqual(first["approved_human_decisions"], 3)

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness_status"], "validation_ready")
            self.assertFalse(manifest["profile"]["final_experiment_freeze"])
            self.assertEqual(manifest["measurement"]["timing"], "not_measured")
            self.assertEqual(manifest["human_decisions"]["approved"], 3)
            self.assertEqual(
                manifest["human_decisions"]["main_sweep_source_scope"],
                "exactly_one_revised_source_per_run",
            )

    def test_scenarios_are_nested_and_every_value_changes_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "injections.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            previous: set[str] = set()
            for scenario_id, expected_count in (
                ("validation_001", 1),
                ("validation_002", 2),
                ("validation_004", 4),
                ("validation_007", 7),
                ("validation_014", 14),
            ):
                scenario = [row for row in rows if row["scenario_id"] == scenario_id]
                cells = {row["cell_id"] for row in scenario}
                self.assertEqual(len(cells), expected_count)
                self.assertTrue(previous.issubset(cells))
                for row in scenario:
                    before = Decimal(row["before_value_decimal"])
                    after = Decimal(row["after_value_decimal"])
                    delta = Decimal(row["delta_decimal"])
                    expected_step = Decimal(1).scaleb(-int(row["published_decimal_places"]))
                    self.assertEqual(after - before, delta)
                    self.assertEqual(abs(delta), expected_step)
                    self.assertNotEqual(after, before)
                    self.assertEqual(row["provenance_class"], "synthetic_not_official")
                    self.assertEqual(row["synthetic_source_id"], "synthetic_revision_harness")
                    self.assertIn(row["revised_source_id"], {"bps_webapi", "bps_tpb_2025"})
                previous = cells

    def test_all_four_treatments_share_each_scenario_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "routes.csv").open(newline="", encoding="utf-8") as handle:
                routes = list(csv.DictReader(handle))

            for scenario_id in {row["scenario_id"] for row in routes}:
                scenario = [row for row in routes if row["scenario_id"] == scenario_id]
                self.assertEqual({row["treatment_id"] for row in scenario}, {"B0", "B1", "B2", "B3"})
                self.assertEqual(len({row["workload_sha256"] for row in scenario}), 1)
                self.assertEqual(len({row["canonical_input_path"] for row in scenario}), 1)
                self.assertEqual({row["execution_status"] for row in scenario}, {"prepared_not_run"})

    def test_contract_rejects_runtime_randomness_and_premature_freeze(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h8b-injected-revision-harness.json").read_text(encoding="utf-8")
        )
        contract["selection"]["random_runtime_state"] = True
        with self.assertRaisesRegex(ValueError, "deterministic"):
            validate_contract(contract)

        contract = json.loads(
            (ROOT / "contracts/h8b-injected-revision-harness.json").read_text(encoding="utf-8")
        )
        contract["scenario_profile"]["final_experiment_freeze"] = True
        with self.assertRaisesRegex(ValueError, "must not claim"):
            validate_contract(contract)

    def test_human_decision_registry_rejects_unapproved_change(self) -> None:
        with (ROOT / "config/h8b/human_decisions.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            decisions = list(csv.DictReader(handle))
        decisions[2]["status"] = "pending"
        with self.assertRaisesRegex(ValueError, "not approved"):
            validate_human_decisions(decisions)


if __name__ == "__main__":
    unittest.main()
