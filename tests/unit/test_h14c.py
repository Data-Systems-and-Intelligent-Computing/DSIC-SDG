from __future__ import annotations

import csv
import json
import os
import unittest
from pathlib import Path

from kkciv_vintage.h14c.pipeline import (
    build_validation,
    cost_of_reproducibility,
    decompose,
    fit_line,
    project_conditions,
    synthesise_failures,
    trend_is_resolved,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("contracts/h14c-breakeven-and-failure-analysis.json")
PROCESSED = Path("results/processed")


def setUpModule() -> None:
    os.chdir(ROOT)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _cost_row(treatment: str, cells: int, seconds: float, byte_value: float, spread: float) -> dict[str, str]:
    return {
        "treatment_id": treatment,
        "cells_revised": str(cells),
        "total_seconds_median": f"{seconds:.3f}",
        "write_seconds_median": f"{seconds - 1:.3f}",
        "write_seconds_min": f"{seconds - 1 - spread:.3f}",
        "write_seconds_max": f"{seconds - 1 + spread:.3f}",
        "maintenance_seconds_median": "1.000",
        "delta_bytes_median": f"{byte_value:.0f}",
        "delta_bytes_min": f"{byte_value - 1:.0f}",
        "delta_bytes_max": f"{byte_value + 1:.0f}",
    }


class ContractTest(unittest.TestCase):
    def test_frozen_contract_is_accepted(self) -> None:
        validate_contract(_contract())

    def test_the_decomposition_must_declare_itself_descriptive(self) -> None:
        contract = _contract()
        contract["decomposition"]["status"] = "fitted_model"
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_a_projection_may_never_become_a_breakeven(self) -> None:
        contract = _contract()
        contract["breakeven"]["projection"]["never"] = "anything goes"
        with self.assertRaises(ValueError):
            validate_contract(contract)


class TrendTest(unittest.TestCase):
    def test_a_monotone_series_with_separated_ends_counts_as_resolved(self) -> None:
        rows = [
            _cost_row("B3", cells, 10.0, 1000 + 100 * cells, spread=0.1)
            for cells in (1, 2, 4, 8, 16, 38)
        ]
        self.assertTrue(trend_is_resolved(rows, treatment="B3", measure="delta_bytes_median"))

    def test_a_series_that_bounces_is_never_resolved(self) -> None:
        seconds = {1: 38.0, 2: 37.5, 4: 36.9, 8: 35.8, 16: 37.5, 38: 35.6}
        rows = [_cost_row("B3", cells, value, 1000, spread=0.1) for cells, value in seconds.items()]
        self.assertFalse(trend_is_resolved(rows, treatment="B3", measure="total_seconds_median"))

    def test_overlapping_ends_are_never_resolved_even_when_monotone(self) -> None:
        rows = [
            _cost_row("B3", cells, 10.0, 1000 + cells, spread=0.1)
            for cells in (1, 2, 4, 8, 16, 38)
        ]
        for row in rows:
            row["delta_bytes_min"] = "900"
            row["delta_bytes_max"] = "1100"
        self.assertFalse(trend_is_resolved(rows, treatment="B3", measure="delta_bytes_median"))


class DecompositionTest(unittest.TestCase):
    def test_a_line_is_recovered_from_its_points(self) -> None:
        slope, intercept = fit_line([(1.0, 12.0), (2.0, 14.0), (4.0, 18.0)])
        self.assertAlmostEqual(slope, 2.0)
        self.assertAlmostEqual(intercept, 10.0)

    def test_the_committed_decomposition_reports_the_frozen_sweep_sizes(self) -> None:
        rows = _read_csv(PROCESSED / "h14c-cost-decomposition.csv")
        self.assertEqual({row["sweep_sizes"] for row in rows}, {"1-2-4-8-16-38"})
        self.assertEqual({row["status"] for row in rows}, {"descriptive"})
        b1 = next(row for row in rows if row["treatment_id"] == "B1" and row["measure"].startswith("total"))
        self.assertEqual(b1["maintenance_share"], "0.0000")


class ProjectionTest(unittest.TestCase):
    def _inputs(self, *, resolved: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        if resolved:
            cost_rows = [
                _cost_row("B3", cells, 10.0, 1000 + 100 * cells, spread=0.1)
                for cells in (1, 2, 4, 8, 16, 38)
            ] + [
                _cost_row("B1", cells, 10.0, 5000 + 10 * cells, spread=0.1)
                for cells in (1, 2, 4, 8, 16, 38)
            ]
        else:
            bouncing = {1: 1000, 2: 1200, 4: 900, 8: 1100, 16: 950, 38: 1050}
            cost_rows = [
                _cost_row(treatment, cells, 10.0, value, spread=5.0)
                for treatment in ("B3", "B1")
                for cells, value in bouncing.items()
            ]
        measured = [
            {
                "comparison": "B3 against B1",
                "measure": "delta_bytes_median",
                "incremental_treatment": "B3",
                "comparator_treatment": "B1",
                "crossing_cells": "none",
                "direction": "B3_cheaper_over_the_whole_sweep",
            }
        ]
        return cost_rows, measured

    def test_a_resolved_trend_yields_a_labelled_projection(self) -> None:
        cost_rows, measured = self._inputs(resolved=True)
        decomposition = decompose(cost_rows, ["total_seconds_median", "delta_bytes_median"])
        rows = project_conditions(
            decomposition=decomposition,
            measured=measured,
            cost_rows=cost_rows,
            largest_measured_size=38,
            panel_cells=5378,
        )
        self.assertEqual(rows[0]["projection_status"], "outside_measured_range")
        self.assertTrue(rows[0]["projected_crossing_cells"])
        self.assertEqual(rows[0]["measured_crossing"], "none")

    def test_an_unresolved_trend_yields_no_number_at_all(self) -> None:
        cost_rows, measured = self._inputs(resolved=False)
        decomposition = decompose(cost_rows, ["total_seconds_median", "delta_bytes_median"])
        rows = project_conditions(
            decomposition=decomposition,
            measured=measured,
            cost_rows=cost_rows,
            largest_measured_size=38,
            panel_cells=5378,
        )
        self.assertEqual(rows[0]["projection_status"], "flat_within_the_measured_ranges")
        self.assertEqual(rows[0]["projected_crossing_cells"], "")

    def test_the_committed_time_comparisons_carry_no_projection(self) -> None:
        rows = [
            row
            for row in _read_csv(PROCESSED / "h14c-breakeven-conditions.csv")
            if row["measure"].startswith("total_seconds")
        ]
        self.assertEqual({row["projected_crossing_cells"] for row in rows}, {""})
        self.assertEqual({row["measured_crossing"] for row in rows}, {"none"})


class SynthesisTest(unittest.TestCase):
    def test_full_recall_with_a_material_failure_is_fatal(self) -> None:
        audit = [
            {"scale": "panel", "treatment_id": treatment, "success_rate": "1.0000", "failures": "0"}
            for treatment in ("B0", "B1", "B2", "B3")
        ]
        profile = [
            {
                "treatment_id": "B0",
                "failure_kind": "overwritten_by_later_vintage",
                "failures": "5",
                "material_failures": "5",
            }
        ]
        decomposition = decompose(
            [
                _cost_row(treatment, cells, 10.0, 1000, spread=0.1)
                for treatment in ("B0", "B1", "B2", "B3")
                for cells in (1, 38)
            ],
            ["total_seconds_median", "delta_bytes_median"],
        )
        reads = [
            {"scenario_id": "sweep_038", "treatment_id": treatment, "bytes_read": "1"}
            for treatment in ("B0", "B1", "B2", "B3")
        ]
        with self.assertRaises(ValueError):
            cost_of_reproducibility(
                audit=audit,
                profile=profile,
                cases=[],
                decomposition=decomposition,
                cost_rows=[],
                reads=reads,
                real_cost=[],
            )

    def test_the_committed_synthesis_prices_every_failure_kind(self) -> None:
        rows = _read_csv(PROCESSED / "h14c-failure-synthesis.csv")
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertTrue(row["price_of_avoiding_it"])
            self.assertTrue(row["treatments_free_of_it"])
        costs = _read_csv(PROCESSED / "h14c-cost-of-reproducibility.csv")
        keeping = {row["treatment_id"] for row in costs if row["panel_failures"] == "0"}
        self.assertEqual(keeping, {"B1", "B3"})


if __name__ == "__main__":
    unittest.main()
