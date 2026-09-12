from __future__ import annotations

import csv
import json
import os
import unittest
from pathlib import Path

from kkciv_vintage.h12.pipeline import (
    aggregate_arrival_cost,
    audit_footprint,
    audit_states,
    audit_timing,
    expected_states,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("contracts/h12-real-revision-cost.json")
CATALOG = Path("results/processed/h11-b1-state-catalog.csv")
TABLES = {
    "B0": ["kkciv.sweep.b0_panel_current"],
    "B1": ["kkciv.sweep.b1_panel_full_snapshots"],
    "B2": ["kkciv.sweep.b2_panel_selected"],
    "B3": ["kkciv.sweep.b3_panel_observation_vintages", "kkciv.sweep.b3_panel_current"],
}


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

    def test_the_four_real_releases_are_not_negotiable(self) -> None:
        contract = _contract()
        contract["workload"]["arrivals"] = 3
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_injected_revisions_cannot_enter_h12(self) -> None:
        contract = _contract()
        contract["measurement_boundary"]["revision_kind"] = "injected"
        with self.assertRaises(ValueError):
            validate_contract(contract)


class ExpectationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.expectations = expected_states(_read_csv(CATALOG))

    def test_the_last_arrival_reproduces_the_panel_baseline(self) -> None:
        baseline = {
            row["table"]: row["expected_rows"]
            for row in _read_csv(Path("results/processed/h11-baseline-expectations.csv"))
        }
        self.assertEqual(self.expectations[("B0", "4")]["rows"], baseline["kkciv.sweep.b0_panel_current"])
        self.assertEqual(
            self.expectations[("B1", "4")]["rows"], baseline["kkciv.sweep.b1_panel_full_snapshots"]
        )
        self.assertEqual(
            self.expectations[("B3_store", "4")]["rows"],
            baseline["kkciv.sweep.b3_panel_observation_vintages"],
        )
        self.assertEqual(
            self.expectations[("B3_serving", "4")]["rows"], baseline["kkciv.sweep.b3_panel_current"]
        )

    def test_b1_accumulates_a_state_per_release_while_b0_does_not(self) -> None:
        b1 = [int(self.expectations[("B1", str(order))]["rows"]) for order in range(1, 5)]
        b0 = [int(self.expectations[("B0", str(order))]["rows"]) for order in range(1, 5)]
        self.assertEqual(b1, sorted(b1))
        self.assertGreater(b1[-1], b0[-1])
        self.assertEqual(
            [self.expectations[("B1", str(order))]["snapshots"] for order in range(1, 5)],
            ["1", "2", "3", "4"],
        )


class AuditTest(unittest.TestCase):
    def _timing_lines(self) -> list[list[str]]:
        labels = {
            "B0": [("merge_arrival", "write"), ("expire_snapshots", "maintenance"), ("verify_state", "verification")],
            "B1": [("insert_overwrite_all_states", "write"), ("verify_state", "verification")],
            "B2": [
                ("narrow_candidates", "harness"),
                ("insert_overwrite_selection", "write"),
                ("expire_snapshots", "maintenance"),
                ("verify_state", "verification"),
            ],
            "B3": [
                ("insert_store_rows", "write"),
                ("merge_serving_dirty_cells", "write"),
                ("expire_snapshots_store", "maintenance"),
                ("expire_snapshots_serving", "maintenance"),
                ("verify_store", "verification"),
                ("verify_serving", "verification"),
            ],
        }
        lines = []
        for treatment, statements in labels.items():
            lines.append(["H12T", "1", treatment, "0", "0", "staging_views", "harness", "1.000"])
            for arrival in range(1, 5):
                for index, (label, phase) in enumerate(statements, start=1):
                    lines.append(
                        ["H12T", "1", treatment, str(arrival), str(index), label, phase, "2.000"]
                    )
        return lines

    def test_the_frozen_statement_sequence_is_required(self) -> None:
        lines = self._timing_lines()
        rows = audit_timing(lines, repetitions=1, arrivals=4)
        self.assertEqual(len(rows), len(lines))
        with self.assertRaises(ValueError):
            audit_timing(lines[:-1], repetitions=1, arrivals=4)

    def test_a_state_that_differs_from_the_panel_is_fatal(self) -> None:
        expectations = expected_states(_read_csv(CATALOG))
        good = [
            [
                "H12A",
                "1",
                "B0",
                "kkciv.sweep.b0_panel_current",
                str(order),
                expectations[("B0", str(order))]["rows"],
                expectations[("B0", str(order))]["cells"],
                "1",
                "100",
                "10",
            ]
            for order in range(1, 5)
        ]
        rows = audit_states(
            good, repetitions=1, arrivals=4, expectations=expectations, tables=TABLES
        )
        self.assertEqual(len(rows), 4)
        broken = [list(row) for row in good]
        broken[2][5] = "1"
        with self.assertRaises(ValueError):
            audit_states(
                broken, repetitions=1, arrivals=4, expectations=expectations, tables=TABLES
            )

    def test_a_metadata_size_that_the_object_store_contradicts_is_fatal(self) -> None:
        footprint = [
            ["H12F", "1", "B0", "t", "data", "s3://bucket/data/a.parquet", "100"],
            ["H12F", "1", "B0", "t", "metadata_json", "s3://bucket/metadata/v1.json", ""],
        ]
        listing = [
            ["H12L", "1", "B0", "t", "s3://bucket/data/a.parquet", "100"],
            ["H12L", "1", "B0", "t", "s3://bucket/metadata/v1.json", "20"],
        ]
        rows = audit_footprint(footprint_lines=footprint, listing_lines=listing, repetitions=1)
        self.assertEqual(rows[0]["total_bytes"], "120")
        self.assertEqual(rows[0]["unreferenced_objects"], "0")
        with self.assertRaises(ValueError):
            audit_footprint(
                footprint_lines=[["H12F", "1", "B0", "t", "data", "s3://bucket/data/a.parquet", "99"]],
                listing_lines=listing,
                repetitions=1,
            )

    def test_an_object_no_metadata_references_is_reported_but_never_counted(self) -> None:
        footprint = [["H12F", "1", "B0", "t", "data", "s3://bucket/data/a.parquet", "100"]]
        listing = [
            ["H12L", "1", "B0", "t", "s3://bucket/data/a.parquet", "100"],
            ["H12L", "1", "B0", "t", "s3://bucket/data/orphan.parquet", "500"],
        ]
        rows = audit_footprint(footprint_lines=footprint, listing_lines=listing, repetitions=1)
        self.assertEqual(rows[0]["total_bytes"], "100")
        self.assertEqual(rows[0]["unreferenced_objects"], "1")
        self.assertEqual(rows[0]["unreferenced_bytes"], "500")


class CostTest(unittest.TestCase):
    def test_write_and_maintenance_are_summed_per_arrival(self) -> None:
        catalog = _read_csv(CATALOG)
        timing = []
        states = []
        for arrival in range(1, 5):
            timing.extend(
                [
                    {
                        "repetition": "1",
                        "treatment_id": "B0",
                        "arrival_order": str(arrival),
                        "statement_index": "1",
                        "statement_label": "merge_arrival",
                        "phase": "write",
                        "seconds": "10.000",
                    },
                    {
                        "repetition": "1",
                        "treatment_id": "B0",
                        "arrival_order": str(arrival),
                        "statement_index": "2",
                        "statement_label": "expire_snapshots",
                        "phase": "maintenance",
                        "seconds": "5.000",
                    },
                ]
            )
            states.append(
                {
                    "repetition": "1",
                    "treatment_id": "B0",
                    "table": "kkciv.sweep.b0_panel_current",
                    "arrival_order": str(arrival),
                    "rows": "10",
                    "cells": "10",
                    "snapshots": "1",
                    "data_bytes": str(1000 * arrival),
                    "manifest_bytes": "0",
                }
            )
        rows = [
            row
            for row in aggregate_arrival_cost(
                timing_rows=timing, state_rows=states, catalog=catalog, repetitions=1
            )
            if row["treatment_id"] == "B0"
        ]
        self.assertEqual([row["total_seconds_median"] for row in rows], ["15.000"] * 4)
        self.assertEqual([row["referenced_bytes_added"] for row in rows], ["1000"] * 4)
        self.assertEqual(rows[0]["arriving_rows"], catalog[0]["input_rows"])
        self.assertEqual(rows[0]["value_changed_rows"], catalog[0]["value_changed_rows"])


if __name__ == "__main__":
    unittest.main()
