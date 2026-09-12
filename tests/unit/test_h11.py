from __future__ import annotations

import csv
import json
import os
import unittest
from pathlib import Path

from kkciv_vintage.h11.pipeline import (
    PANEL_ARRIVALS,
    arrival_order,
    audit_injection,
    audit_recall,
    audit_timing,
    build_sweep_payload,
    deduplicate_panel,
    find_breakeven,
    full_snapshot_states,
    rank_universe,
    validate_contract,
    validate_human_decisions,
    verify_freeze,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("contracts/h11-main-sweep.json")
DECISIONS = Path("config/h10c/human_decisions.csv")
FREEZE = Path("config/experiments/experiment_freeze.csv")
PROCESSED = Path("results/processed")


def setUpModule() -> None:
    os.chdir(ROOT)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _panel_row(**overrides: str) -> dict[str, str]:
    row = {
        "ingestion_batch_id": "h4-2981e0fb3bc2d960",
        "input_dataset": "h3_province_webapi",
        "domain": "economy",
        "source_id": "bps_webapi",
        "indicator_key": "sdg08_productivity_growth",
        "series_key": "total",
        "release_date": "2026-09-08",
        "observed_period": "2025",
        "geo_level": "province",
        "geo_code": "1300",
        "geo_name": "Sumatera Barat",
        "unit": "percent",
        "value": "0.16",
        "producer": "Badan Pusat Statistik",
        "methodology_version": "webapi-var-1161",
        "source_record_id": "domain=0000;var=1161;vervar=13;turvar=0;th=125;turth=0",
    }
    row.update(overrides)
    return row


class ContractTest(unittest.TestCase):
    def test_frozen_contract_is_accepted(self) -> None:
        validate_contract(_contract())

    def test_the_sweep_must_keep_the_frozen_sizes(self) -> None:
        contract = _contract()
        contract["scenarios"] = contract["scenarios"][:-1]
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_the_panel_shape_is_not_negotiable(self) -> None:
        contract = _contract()
        contract["panel"]["cells"] = 5000
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_a_smoke_status_cannot_claim_the_main_sweep(self) -> None:
        contract = _contract()
        contract["measurement_boundary"]["sweep_status"] = "physical_smoke"
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_the_five_reviewer_decisions_are_recorded_as_approved(self) -> None:
        validate_human_decisions(_read_csv(DECISIONS))

    def test_an_unapproved_decision_is_rejected(self) -> None:
        rows = _read_csv(DECISIONS)
        rows[0] = {**rows[0], "status": "proposed"}
        with self.assertRaises(ValueError):
            validate_human_decisions(rows)


class FreezeTest(unittest.TestCase):
    def test_every_frozen_evidence_file_still_matches(self) -> None:
        contract = _contract()
        checked = verify_freeze(_read_csv(FREEZE), contract["freeze"]["required_freeze_ids"])
        self.assertEqual(len(checked), len(_read_csv(FREEZE)))

    def test_a_changed_checksum_stops_the_sweep(self) -> None:
        rows = _read_csv(FREEZE)
        rows[0] = {**rows[0], "evidence_sha256": "0" * 64}
        with self.assertRaises(ValueError):
            verify_freeze(rows, [])

    def test_a_missing_frozen_item_stops_the_sweep(self) -> None:
        with self.assertRaises(ValueError):
            verify_freeze(_read_csv(FREEZE), ["F9.9"])


class DeduplicationTest(unittest.TestCase):
    def test_the_later_retrieval_wins_and_the_duplicate_is_documented(self) -> None:
        older = _panel_row(input_dataset="h3_province_webapi")
        newer = _panel_row(
            input_dataset="h3_release_reconciliation",
            source_record_id="domain=0000;var=1983;vervar=13;turvar=0;th=125;turth=0",
        )
        kept, duplicates = deduplicate_panel(
            [older, newer],
            retrieved_at_for=lambda row: {
                "h3_province_webapi": "2026-09-08T14:04:19+00:00",
                "h3_release_reconciliation": "2026-09-08T23:38:59+00:00",
            }[row["input_dataset"]],
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["input_dataset"], "h3_release_reconciliation")
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["values_identical"], "yes")
        self.assertEqual(duplicates[0]["dropped_input_dataset"], "h3_province_webapi")

    def test_a_duplicate_with_another_value_is_never_dropped(self) -> None:
        with self.assertRaises(ValueError):
            deduplicate_panel(
                [_panel_row(), _panel_row(value="0.17", source_record_id="var=1983")],
                retrieved_at_for=lambda row: "2026-09-08T14:04:19+00:00",
            )

    def test_the_committed_panel_keeps_its_frozen_shape(self) -> None:
        observations = _read_csv(PROCESSED / "h11-panel-observations.csv")
        duplicates = _read_csv(PROCESSED / "h11-panel-duplicates.csv")
        self.assertEqual(len(observations), 6983)
        self.assertEqual(len({row["cell_id"] for row in observations}), 5378)
        self.assertEqual(len(duplicates), 683)
        self.assertTrue(all(row["values_identical"] == "yes" for row in duplicates))
        keys = [(row["cell_id"], row["vintage_id"]) for row in observations]
        self.assertEqual(len(set(keys)), len(keys))


class PanelStateTest(unittest.TestCase):
    def test_the_panel_arrives_in_four_releases(self) -> None:
        vintages = _read_csv(PROCESSED / "h11-panel-vintages.csv")
        self.assertEqual(len(vintages), PANEL_ARRIVALS)
        orders = arrival_order(vintages)
        self.assertEqual(sorted(orders.values()), [1, 2, 3, 4])
        self.assertEqual(
            [row["arrival_order"] for row in sorted(vintages, key=lambda item: orders[item["vintage_id"]])],
            ["1", "2", "3", "4"],
        )

    def test_b1_states_grow_with_the_panel_instead_of_assuming_equal_releases(self) -> None:
        vintages = [
            {
                "vintage_id": "v1",
                "source_id": "a",
                "vintage_date": "2024-01-01",
                "retrieved_at": "2024-01-01T00:00:00+00:00",
            },
            {
                "vintage_id": "v2",
                "source_id": "b",
                "vintage_date": "2025-01-01",
                "retrieved_at": "2025-01-01T00:00:00+00:00",
            },
        ]
        observations = [
            {"observation_id": "o1", "cell_id": "c1", "vintage_id": "v1", "value_decimal": "1.0"},
            {"observation_id": "o2", "cell_id": "c1", "vintage_id": "v2", "value_decimal": "2.0"},
            {"observation_id": "o3", "cell_id": "c2", "vintage_id": "v2", "value_decimal": "3.0"},
        ]
        catalog, states = full_snapshot_states(vintages, observations)
        self.assertEqual([row["state_rows"] for row in catalog], ["1", "2"])
        self.assertEqual(len(states), 3)
        self.assertEqual(
            {row["observation_id"] for row in states if row["snapshot_order"] == "2"},
            {"o2", "o3"},
        )

    def test_the_committed_b1_catalog_matches_the_panel(self) -> None:
        catalog = _read_csv(PROCESSED / "h11-b1-state-catalog.csv")
        states = sum(int(row["state_rows"]) for row in catalog)
        baseline = _read_csv(PROCESSED / "h11-baseline-expectations.csv")
        expected = next(
            row for row in baseline if row["table"].endswith("b1_panel_full_snapshots")
        )
        self.assertEqual(str(states), expected["expected_rows"])
        self.assertEqual(catalog[-1]["state_rows"], "5378")


class SweepPayloadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.universe = _read_csv(Path("config/experiments/main_sweep_universe.csv"))
        self.scenarios = _read_csv(Path("config/experiments/main_sweep_scenarios.csv"))
        self.base_by_cell = {
            row["cell_id"]: {
                **row,
                "observation_id": f"obs-{row['cell_id']}",
                "vintage_id": "vintage-webapi",
                "value_decimal": f"{float(row['base_value_lexeme']):.10f}",
                "value_lexeme": row["base_value_lexeme"],
                "published_decimal_places": "2",
                "period_granularity": "year",
                "domain": "economy",
            }
            for row in self.universe
        }
        self.source_by_vintage = {"vintage-webapi": "bps_webapi"}
        self.contract_universe = _contract()["universe"]

    def test_the_frozen_ranking_is_reproduced_from_the_seed(self) -> None:
        ranked = rank_universe([row["cell_id"] for row in self.universe], "20260912")
        frozen = [
            row["cell_id"] for row in sorted(self.universe, key=lambda item: int(item["selection_rank"]))
        ]
        self.assertEqual(ranked, frozen)

    def test_the_payload_is_nested_and_revises_one_source(self) -> None:
        plans, injections = build_sweep_payload(
            scenarios=self.scenarios,
            universe=self.universe,
            base_by_cell=self.base_by_cell,
            source_by_vintage=self.source_by_vintage,
            contract_universe=self.contract_universe,
        )
        self.assertEqual([row["selection_count"] for row in plans], ["1", "2", "4", "8", "16", "38"])
        previous: set[str] = set()
        for plan in plans:
            cells = {
                row["cell_id"] for row in injections if row["scenario_id"] == plan["scenario_id"]
            }
            self.assertTrue(previous.issubset(cells))
            previous = cells
        self.assertEqual({row["revised_source_id"] for row in injections}, {"bps_webapi"})
        self.assertEqual(len(injections), 1 + 2 + 4 + 8 + 16 + 38)

    def test_a_changed_base_value_stops_the_sweep(self) -> None:
        cell_id = self.universe[0]["cell_id"]
        self.base_by_cell[cell_id] = {**self.base_by_cell[cell_id], "value_lexeme": "9.99"}
        with self.assertRaises(ValueError):
            build_sweep_payload(
                scenarios=self.scenarios,
                universe=self.universe,
                base_by_cell=self.base_by_cell,
                source_by_vintage=self.source_by_vintage,
                contract_universe=self.contract_universe,
            )

    def test_the_committed_payload_matches_the_frozen_plan(self) -> None:
        plans = _read_csv(PROCESSED / "h11-sweep-plans.csv")
        injections = _read_csv(PROCESSED / "h11-sweep-injections.csv")
        frozen = _read_csv(Path("config/experiments/main_sweep_scenarios.csv"))
        self.assertEqual(
            [row["selection_count"] for row in plans],
            [row["selection_count"] for row in frozen],
        )
        self.assertEqual(len(injections), 69)
        self.assertEqual({row["mutation_rule"] for row in injections}, {"one_published_unit"})
        self.assertEqual({row["provenance_class"] for row in injections}, {"synthetic_not_official"})
        for row in injections:
            self.assertNotEqual(row["before_value_decimal"], row["after_value_decimal"])


class BreakevenTest(unittest.TestCase):
    def _cost(self, values: dict[str, list[str]]) -> list[dict[str, str]]:
        sizes = [("1", "sweep_001", "0.03"), ("38", "sweep_038", "1.00")]
        rows = []
        for treatment, seconds in values.items():
            for (cells, scenario_id, share), value in zip(sizes, seconds):
                rows.append(
                    {
                        "scenario_id": scenario_id,
                        "treatment_id": treatment,
                        "cells_revised": cells,
                        "selection_share": share,
                        "total_seconds_median": value,
                    }
                )
        return rows

    def test_a_crossing_is_reported_at_the_smallest_swept_size(self) -> None:
        rows = find_breakeven(
            self._cost({"B3": ["10.000", "40.000"], "B1": ["20.000", "20.000"]}),
            ["B3 against B1"],
            ["total_seconds_median"],
        )
        self.assertEqual(rows[0]["cheaper_at_smallest_point"], "yes")
        self.assertEqual(rows[0]["crossing_cells"], "38")
        self.assertEqual(rows[0]["direction"], "B3_cheaper_until_38_cells")

    def test_no_crossing_inside_the_range_is_said_plainly(self) -> None:
        rows = find_breakeven(
            self._cost({"B3": ["10.000", "15.000"], "B1": ["20.000", "20.000"]}),
            ["B3 against B1"],
            ["total_seconds_median"],
        )
        self.assertEqual(rows[0]["crossing_cells"], "none")
        self.assertEqual(rows[0]["direction"], "B3_cheaper_over_the_whole_sweep")

    def test_a_comparator_that_wins_everywhere_is_reported_too(self) -> None:
        rows = find_breakeven(
            self._cost({"B3": ["30.000", "40.000"], "B1": ["20.000", "20.000"]}),
            ["B3 against B1"],
            ["total_seconds_median"],
        )
        self.assertEqual(rows[0]["cheaper_at_smallest_point"], "no")
        self.assertEqual(rows[0]["direction"], "B1_cheaper_over_the_whole_sweep")


class AuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.expectations = _read_csv(PROCESSED / "h11-sweep-scenarios.csv")[:1]
        self.scenario = self.expectations[0]["scenario_id"]

    def _injection_line(self, treatment: str, **overrides: str) -> list[str]:
        expectation = self.expectations[0]
        if treatment == "B3":
            rows = str(
                int(expectation["panel_observations"]) + int(expectation["cells_revised"])
            )
        else:
            rows = expectation[f"{treatment.lower()}_expected_rows"]
        line = {
            "rows": rows,
            "cells": expectation[f"{treatment.lower()}_expected_cells"],
            "snapshots": expectation[f"{treatment.lower()}_expected_snapshots"],
            "mismatch": "0",
            "propagated": expectation[f"{treatment.lower()}_propagated_revisions"],
        }
        line.update(overrides)
        return [
            "H11I",
            "1",
            self.scenario,
            treatment,
            line["rows"],
            line["cells"],
            line["snapshots"],
            line["mismatch"],
            line["propagated"],
            "",
        ]

    def test_one_repetition_of_every_treatment_is_accepted(self) -> None:
        lines = [self._injection_line(treatment) for treatment in ("B0", "B1", "B2", "B3")]
        rows = audit_injection(lines=lines, repetitions=1, expectations=self.expectations)
        self.assertEqual(len(rows), 4)

    def test_a_state_mismatch_is_fatal(self) -> None:
        lines = [self._injection_line(treatment) for treatment in ("B0", "B1", "B2", "B3")]
        lines[0][7] = "1"
        with self.assertRaises(ValueError):
            audit_injection(lines=lines, repetitions=1, expectations=self.expectations)

    def test_a_missing_treatment_is_fatal(self) -> None:
        lines = [self._injection_line(treatment) for treatment in ("B0", "B1", "B2")]
        with self.assertRaises(ValueError):
            audit_injection(lines=lines, repetitions=1, expectations=self.expectations)

    def test_recall_must_agree_between_repetitions(self) -> None:
        expected = [
            {
                "scenario_id": "sweep_001",
                "treatment_id": "B0",
                "request_kind": "official",
                "requests": "10",
                "expected_addressable": "8",
            }
        ]
        agreeing = [
            ["H11R", "1", "sweep_001", "B0", "official", "10", "8", "8"],
            ["H11R", "2", "sweep_001", "B0", "official", "10", "8", "8"],
        ]
        rows = audit_recall(lines=agreeing, expected=expected, repetitions=2)
        self.assertEqual(rows[0]["recall_rate"], "0.8000")
        disagreeing = [agreeing[0], ["H11R", "2", "sweep_001", "B0", "official", "10", "7", "7"]]
        with self.assertRaises(ValueError):
            audit_recall(lines=disagreeing, expected=expected, repetitions=2)

    def test_an_inexact_value_is_never_counted_as_recall(self) -> None:
        expected = [
            {
                "scenario_id": "sweep_001",
                "treatment_id": "B1",
                "request_kind": "official",
                "requests": "10",
                "expected_addressable": "10",
            }
        ]
        with self.assertRaises(ValueError):
            audit_recall(
                lines=[["H11R", "1", "sweep_001", "B1", "official", "10", "10", "9"]],
                expected=expected,
                repetitions=1,
            )

    def test_timing_requires_the_frozen_statements_of_every_treatment(self) -> None:
        lines = [
            ["H11T", "1", "sweep_001", "B0", "0", "staging_views", "harness", "1.0"],
            ["H11T", "1", "sweep_001", "B0", "1", "merge_revision", "write", "2.0"],
            ["H11T", "1", "sweep_001", "B0", "2", "expire_snapshots", "maintenance", "3.0"],
        ]
        with self.assertRaises(ValueError):
            audit_timing(lines, repetitions=1, scenarios=["sweep_001"])


if __name__ == "__main__":
    unittest.main()
