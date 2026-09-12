from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from kkciv_vintage.h13.pipeline import (
    apply_doubt_rule,
    build_validation,
    pool_measurements,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("contracts/h13-rerun-stability.json")


def setUpModule() -> None:
    os.chdir(ROOT)


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _timing(point: str, treatment: str, write: dict[str, float], maintenance: float = 1.0) -> list[dict[str, str]]:
    rows = []
    for repetition, seconds in write.items():
        rows.append(
            {
                "repetition": repetition,
                "scenario_id": point,
                "treatment_id": treatment,
                "statement_label": "write_statement",
                "phase": "write",
                "seconds": f"{seconds}",
            }
        )
        rows.append(
            {
                "repetition": repetition,
                "scenario_id": point,
                "treatment_id": treatment,
                "statement_label": "expire_snapshots",
                "phase": "maintenance",
                "seconds": f"{maintenance}",
            }
        )
    return rows


class ContractTest(unittest.TestCase):
    def test_frozen_contract_is_accepted(self) -> None:
        validate_contract(_contract())

    def test_a_rule_chosen_after_the_fact_is_rejected(self) -> None:
        contract = _contract()
        contract["doubt_rule"]["rule_fixed_before_selection"] = False
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_the_reported_median_may_never_be_replaced(self) -> None:
        contract = _contract()
        contract["verdict"]["reported_medians_stay"] = "the pooled median replaces the reported one"
        with self.assertRaises(ValueError):
            validate_contract(contract)


class DoubtRuleTest(unittest.TestCase):
    def test_a_point_above_the_threshold_is_flagged_and_routed_to_a_rerun_unit(self) -> None:
        rows = apply_doubt_rule(
            stage="H11",
            point_kind="sweep_scenario",
            point_field="scenario_id",
            timing_rows=_timing("sweep_001", "B2", {"1": 10.0, "2": 10.0, "3": 14.0}),
            threshold=0.20,
            rerun_unit=lambda point: point,
        )
        self.assertEqual(rows[0]["doubtful"], "yes")
        self.assertEqual(rows[0]["rerun_unit"], "sweep_001")
        self.assertEqual(rows[0]["write_seconds_median"], "10.000")
        self.assertEqual(rows[0]["write_spread_ratio"], "0.4000")

    def test_a_steady_point_is_left_alone(self) -> None:
        rows = apply_doubt_rule(
            stage="H11",
            point_kind="sweep_scenario",
            point_field="scenario_id",
            timing_rows=_timing("sweep_002", "B1", {"1": 10.0, "2": 10.5, "3": 10.2}),
            threshold=0.20,
            rerun_unit=lambda point: point,
        )
        self.assertEqual(rows[0]["doubtful"], "no")
        self.assertEqual(rows[0]["rerun_unit"], "")

    def test_only_the_write_phase_decides(self) -> None:
        rows = apply_doubt_rule(
            stage="H11",
            point_kind="sweep_scenario",
            point_field="scenario_id",
            timing_rows=[
                *_timing("sweep_003", "B0", {"1": 10.0, "2": 10.1}, maintenance=1.0),
                {
                    "repetition": "3",
                    "scenario_id": "sweep_003",
                    "treatment_id": "B0",
                    "statement_label": "write_statement",
                    "phase": "write",
                    "seconds": "10.05",
                },
                {
                    "repetition": "3",
                    "scenario_id": "sweep_003",
                    "treatment_id": "B0",
                    "statement_label": "expire_snapshots",
                    "phase": "maintenance",
                    "seconds": "40.0",
                },
            ],
            threshold=0.20,
            rerun_unit=lambda point: point,
        )
        self.assertEqual(rows[0]["doubtful"], "no")
        self.assertEqual(rows[0]["maintenance_spread_ratio"], "39.0000")


class PoolingTest(unittest.TestCase):
    def _pool(self, added: dict[str, float]) -> dict[str, str]:
        reported = _timing("sweep_001", "B2", {"1": 10.0, "2": 10.0, "3": 14.0})
        doubt = apply_doubt_rule(
            stage="H11",
            point_kind="sweep_scenario",
            point_field="scenario_id",
            timing_rows=reported,
            threshold=0.20,
            rerun_unit=lambda point: point,
        )
        return pool_measurements(
            doubt_rows=doubt,
            reported={"H11": reported},
            extra={"H11": _timing("sweep_001", "B2", added)},
            point_fields={"H11": "scenario_id"},
            stable_within=0.05,
        )[0]

    def test_a_pooled_median_inside_the_band_leaves_the_reported_number_standing(self) -> None:
        row = self._pool({"1": 10.1, "2": 10.2, "3": 10.3})
        self.assertEqual(row["repetitions_pooled"], "6")
        self.assertEqual(row["write_median_reported"], "10.000")
        self.assertEqual(row["write_median_pooled"], "10.150")
        self.assertEqual(row["verdict"], "stable")

    def test_a_pooled_median_outside_the_band_is_reported_as_shifted(self) -> None:
        row = self._pool({"1": 14.0, "2": 14.5, "3": 15.0})
        self.assertEqual(row["verdict"], "shifted")
        self.assertGreater(float(row["shift_ratio"]), 0.05)

    def test_a_point_that_was_not_rerun_keeps_its_reported_numbers_only(self) -> None:
        reported = _timing("sweep_002", "B1", {"1": 10.0, "2": 10.1, "3": 10.2})
        doubt = apply_doubt_rule(
            stage="H11",
            point_kind="sweep_scenario",
            point_field="scenario_id",
            timing_rows=reported,
            threshold=0.20,
            rerun_unit=lambda point: point,
        )
        row = pool_measurements(
            doubt_rows=doubt,
            reported={"H11": reported},
            extra={"H11": []},
            point_fields={"H11": "scenario_id"},
            stable_within=0.05,
        )[0]
        self.assertEqual(row["verdict"], "not_rerun")
        self.assertEqual(row["repetitions_added"], "0")
        self.assertEqual(row["write_median_pooled"], "")


class ValidationTest(unittest.TestCase):
    def _rows(self, rerun: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        doubt = [
            {
                "stage": "H11",
                "point_kind": "sweep_scenario",
                "point": "sweep_001",
                "treatment_id": "B2",
                "doubtful": "yes",
                "rerun_unit": "sweep_001",
                "write_seconds_median": "10.000",
                "write_spread_ratio": "0.4000",
                "repetitions": "3",
            }
        ]
        stability = [
            {
                "stage": "H11",
                "point": "sweep_001",
                "treatment_id": "B2",
                "was_doubtful": "yes",
                "repetitions_reported": "3",
                "write_median_reported": "10.000",
                "write_spread_reported": "0.4000",
                "repetitions_added": "3" if rerun else "0",
                "repetitions_pooled": "6" if rerun else "3",
                "write_median_pooled": "10.150" if rerun else "",
                "shift_ratio": "0.0150" if rerun else "",
                "verdict": "stable" if rerun else "not_rerun",
            }
        ]
        return doubt, stability

    def test_a_doubtful_point_that_was_never_rerun_fails_the_audit(self) -> None:
        doubt, stability = self._rows(rerun=False)
        rows = build_validation(
            contract=_contract(),
            doubt_rows=doubt,
            stability_rows=stability,
            environments={"h11_rerun": {"host_nproc": "2", "git_dirty_entries": "0"}},
            state_checks={"H11": 4},
        )
        self.assertIn("fail", {row["status"] for row in rows})

    def test_a_complete_rerun_on_the_frozen_node_passes(self) -> None:
        doubt, stability = self._rows(rerun=True)
        rows = build_validation(
            contract=_contract(),
            doubt_rows=doubt,
            stability_rows=stability,
            environments={"h11_rerun": {"host_nproc": "2", "git_dirty_entries": "0"}},
            state_checks={"H11": 4},
        )
        self.assertEqual({row["status"] for row in rows}, {"pass"})

    def test_a_dirty_working_tree_fails_the_audit(self) -> None:
        doubt, stability = self._rows(rerun=True)
        rows = build_validation(
            contract=_contract(),
            doubt_rows=doubt,
            stability_rows=stability,
            environments={"h11_rerun": {"host_nproc": "2", "git_dirty_entries": "3"}},
            state_checks={"H11": 4},
        )
        self.assertIn("fail", {row["status"] for row in rows})


if __name__ == "__main__":
    unittest.main()
