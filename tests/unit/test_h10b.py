from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h10b.pipeline import (
    aggregate_apply_cost,
    run_aggregate,
    audit_injection,
    audit_orphan_cleanup,
    audit_recall,
    measure_phases,
    run_prepare,
    validate_contract,
    validate_human_decisions,
)


ROOT = Path(__file__).resolve().parents[2]
# The payload records repository-relative paths, so the pipeline is driven from the root.
CONTRACT = Path("contracts/h10b-injected-revision-physical.json")
DECISIONS = Path("config/h10/human_decisions.csv")
PROCESSED = Path("results/processed")


def setUpModule() -> None:
    os.chdir(ROOT)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _prepare(output: Path) -> dict[str, object]:
    return run_prepare(
        contract_path=CONTRACT,
        decisions_path=DECISIONS,
        h6_manifest_path=Path("data/manifests/h6-vintage-schema.json"),
        h6b_manifest_path=Path("data/manifests/h6b-source-trust.json"),
        h6c_manifest_path=Path("data/manifests/h6c-cell-lineage.json"),
        h8b_manifest_path=Path("data/manifests/h8b-injected-revision-harness.json"),
        h9b_contract_path=Path("contracts/h9b-small-revision-execution.json"),
        h9b_manifest_path=Path("data/manifests/h9b-small-revision-execution.json"),
        b2_contract_path=Path("contracts/h7b-b2-single-source.json"),
        scenarios_output=output / "scenarios.csv",
        store_output=output / "store.csv",
        b1_output=output / "b1.csv",
        b2_output=output / "b2.csv",
        dirty_output=output / "dirty.csv",
        expected_state_output=output / "state.csv",
        expected_recall_output=output / "recall.csv",
        manifest_output=output / "manifest.json",
    )


def _scenarios() -> list[dict[str, str]]:
    return _read_csv(PROCESSED / "h10b-physical-scenarios.csv")


def _injection_lines(**overrides: str) -> list[list[str]]:
    lines = []
    for rep in ("1", "2", "3"):
        for scenario, cells in (("validation_001", 1), ("validation_002", 2)):
            for treatment in ("B0", "B1", "B2", "B3"):
                snapshots = "4" if treatment == "B1" else "1"
                store_rows = str(38 + cells) if treatment == "B3" else ""
                store_snapshots = "1" if treatment == "B3" else ""
                lines.append(
                    [
                        "H10BI",
                        rep,
                        scenario,
                        treatment,
                        overrides.get("rows", "14"),
                        "14",
                        overrides.get("snapshots", snapshots),
                        overrides.get("mismatches", "0"),
                        store_rows,
                        store_snapshots,
                    ]
                )
    return lines


def _recall_fixture() -> tuple[list[list[str]], list[dict[str, str]], list[list[str]]]:
    expected = [
        {
            "scenario_id": "validation_001",
            "treatment_id": "B0",
            "requested_observation_id": "obs_a",
            "request_kind": "official",
            "cell_id": "cell_a",
            "requested_value_lexeme": "1.19",
            "expected_addressable": "yes",
        },
        {
            "scenario_id": "validation_001",
            "treatment_id": "B0",
            "requested_observation_id": "obs_b",
            "request_kind": "official",
            "cell_id": "cell_b",
            "requested_value_lexeme": "2.50",
            "expected_addressable": "no",
        },
    ]
    lines = []
    for rep in ("1", "2"):
        lines.append(["H10BR", rep, "validation_001", "B0", "obs_a", "obs_a", "1.19", "current"])
        lines.append(["H10BR", rep, "validation_001", "B0", "obs_b", "", "", "current"])
    counts = [["H10BSNAPCOUNT", rep, "validation_001", "4"] for rep in ("1", "2")]
    return lines, expected, counts


class H10BPreparationTest(unittest.TestCase):
    def test_prepare_reproduces_the_committed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            result = _prepare(output)
            self.assertEqual(result["scenarios"], 2)
            self.assertEqual(result["synthetic_rows"], 3)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        committed = {
            "scenarios.csv": "h10b-physical-scenarios.csv",
            "store.csv": "h10b-synthetic-observations.csv",
            "b1.csv": "h10b-b1-next-state.csv",
            "b2.csv": "h10b-b2-next-state.csv",
            "dirty.csv": "h10b-b3-dirty-cells.csv",
            "state.csv": "h10b-expected-state.csv",
            "recall.csv": "h10b-expected-recall.csv",
        }
        by_name = {Path(item["path"]).name: item for item in manifest["outputs"]}
        for produced, published in committed.items():
            with self.subTest(output=published):
                self.assertEqual(
                    by_name[produced]["sha256"],
                    next(
                        item["sha256"]
                        for item in json.loads(
                            Path("data/manifests/h10b-physical-payload.json").read_text(encoding="utf-8")
                        )["outputs"]
                        if Path(item["path"]).name == published
                    ),
                )

    def test_payload_serves_the_frozen_logical_outcome(self) -> None:
        state = _read_csv(PROCESSED / "h10b-expected-state.csv")
        logical = {
            (row["scenario_id"], row["treatment_id"], row["cell_id"]): row["observation_id"]
            for row in _read_csv(PROCESSED / "h9b-post-revision-states.csv")
        }
        self.assertEqual(len(state), 112)
        for row in state:
            key = (row["scenario_id"], row["treatment_id"], row["cell_id"])
            self.assertEqual(row["observation_id"], logical[key])

    def test_b2_keeps_the_synthetic_row_labeled_as_synthetic(self) -> None:
        synthetic = [
            row
            for row in _read_csv(PROCESSED / "h10b-b2-next-state.csv")
            if row["producer"] == "synthetic_revision_harness"
        ]
        self.assertEqual(len(synthetic), 1)
        self.assertEqual(synthetic[0]["scenario_id"], "validation_002")
        self.assertEqual(synthetic[0]["evidence_level"], "synthetic_not_official")
        # The score comes from the revised source; the row never claims BPS as producer.
        self.assertEqual(synthetic[0]["selected_source_id"], "bps_tpb_2025")

    def test_synthetic_store_rows_arrive_after_the_official_releases(self) -> None:
        for row in _read_csv(PROCESSED / "h10b-synthetic-observations.csv"):
            self.assertEqual(row["arrival_order"], "4")
            self.assertEqual(row["source_id"], "synthetic_revision_harness")
            self.assertEqual(row["vintage_date"], "2026-09-09")


RAW_DIR = Path("results/raw/h10b/h10b-20260912")
CLEANUP_DIR = Path("results/raw/h10b/cleanup-20260912")


@unittest.skipUnless((ROOT / RAW_DIR / "recall.txt").exists(), "the physical run is not committed yet")
class H10BMeasurementTest(unittest.TestCase):
    def _aggregate(self, output: Path) -> dict[str, object]:
        return run_aggregate(
            contract_path=CONTRACT,
            decisions_path=DECISIONS,
            raw_dir=RAW_DIR,
            cleanup_dir=CLEANUP_DIR,
            payload_manifest_path=Path("data/manifests/h10b-physical-payload.json"),
            timing_output=output / "timing.csv",
            apply_cost_output=output / "cost.csv",
            storage_output=output / "storage.csv",
            recall_output=output / "recall.csv",
            orphan_output=output / "orphan.csv",
            validation_output=output / "validation.csv",
            summary_output=output / "summary.csv",
            manifest_output=output / "manifest.json",
        )

    def test_aggregation_is_deterministic_and_matches_the_published_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            first = self._aggregate(output)
            first_manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            second = self._aggregate(output)
            second_manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(first, second)
        self.assertEqual(first_manifest["outputs"], second_manifest["outputs"])
        self.assertEqual(first["status"], "measured")

        published = {
            Path(item["path"]).name: item["sha256"]
            for item in json.loads(
                Path("data/manifests/h10b-injected-revision-physical.json").read_text(encoding="utf-8")
            )["outputs"]
        }
        produced = {
            "timing.csv": "h10b-statement-timing.csv",
            "cost.csv": "h10b-apply-cost.csv",
            "storage.csv": "h10b-storage-delta.csv",
            "recall.csv": "h10b-recall-after-revision.csv",
            "orphan.csv": "h10b-orphan-cleanup.csv",
            "validation.csv": "h10b-validation.csv",
            "summary.csv": "h10b-summary.csv",
        }
        by_name = {Path(item["path"]).name: item["sha256"] for item in first_manifest["outputs"]}
        for local, publishedname in produced.items():
            with self.subTest(output=publishedname):
                self.assertEqual(by_name[local], published[publishedname])

    def test_every_treatment_keeps_its_designed_recall_after_the_revision(self) -> None:
        recall = _read_csv(PROCESSED / "h10b-recall-after-revision.csv")
        for row in recall:
            self.assertEqual(row["addressable"], row["expected_addressable"])
            if row["addressable"] == "yes":
                self.assertEqual(row["returned_value_lexeme"], row["requested_value_lexeme"])
        for scenario, requests in (("validation_001", 39), ("validation_002", 40)):
            for treatment, expected in (("B1", requests), ("B3", requests)):
                addressable = sum(
                    row["addressable"] == "yes"
                    for row in recall
                    if row["scenario_id"] == scenario and row["treatment_id"] == treatment
                )
                self.assertEqual(addressable, expected)


class H10BContractTest(unittest.TestCase):
    def test_contract_and_decisions_guard_the_protocol(self) -> None:
        validate_contract(_contract())
        validate_human_decisions(_read_csv(DECISIONS))

        fewer_repetitions = _contract()
        fewer_repetitions["protocol"]["repetitions"] = 2
        with self.assertRaises(ValueError):
            validate_contract(fewer_repetitions)

        claims_the_sweep = _contract()
        claims_the_sweep["measurement_boundary"]["sweep_status"] = "main_sweep"
        with self.assertRaises(ValueError):
            validate_contract(claims_the_sweep)

        unlinked_timing = _contract()
        unlinked_timing["timing"]["environment_decision"] = "none"
        with self.assertRaises(ValueError):
            validate_contract(unlinked_timing)

        with self.assertRaises(ValueError):
            validate_human_decisions(
                [row for row in _read_csv(DECISIONS) if row["decision_id"] != "h10b_timing_environment"]
            )

        pending = _read_csv(DECISIONS)
        for row in pending:
            if row["decision_id"] == "h10b_orphan_cleanup":
                row["status"] = "pending"
        with self.assertRaises(ValueError):
            validate_human_decisions(pending)


class H10BAuditTest(unittest.TestCase):
    def test_injection_requires_the_logical_state_and_the_designed_snapshots(self) -> None:
        rows = audit_injection(
            lines=_injection_lines(),
            contract=_contract(),
            scenarios=_scenarios(),
            official_requests=38,
        )
        self.assertEqual(len(rows), 24)

        with self.assertRaises(ValueError):
            audit_injection(
                lines=_injection_lines(mismatches="1"),
                contract=_contract(),
                scenarios=_scenarios(),
                official_requests=38,
            )
        with self.assertRaises(ValueError):
            audit_injection(
                lines=_injection_lines(snapshots="2"),
                contract=_contract(),
                scenarios=_scenarios(),
                official_requests=38,
            )

    def test_recall_must_agree_with_the_logical_audit_in_every_repetition(self) -> None:
        lines, expected, counts = _recall_fixture()
        rows = audit_recall(lines=lines, expected=expected, snapshot_counts=counts, repetitions=2)
        self.assertEqual([row["addressable"] for row in rows], ["yes", "no"])
        self.assertEqual(rows[0]["exact_match"], "yes")

        wrong_value = [list(line) for line in lines]
        wrong_value[0][6] = "9.99"
        with self.assertRaises(ValueError):
            audit_recall(lines=wrong_value, expected=expected, snapshot_counts=counts, repetitions=2)

        unexpected_hit = [list(line) for line in lines]
        unexpected_hit[1][5] = "obs_b"
        unexpected_hit[1][6] = "2.50"
        with self.assertRaises(ValueError):
            audit_recall(lines=unexpected_hit, expected=expected, snapshot_counts=counts, repetitions=2)

        missing_snapshot = [["H10BSNAPCOUNT", "1", "validation_001", "3"], counts[1]]
        with self.assertRaises(ValueError):
            audit_recall(lines=lines, expected=expected, snapshot_counts=missing_snapshot, repetitions=2)

    def test_orphan_cleanup_rows_must_add_up(self) -> None:
        counts = [
            ["H10BC", "t0", "before", "5", "500"],
            ["H10BC", "t0", "after", "3", "300"],
        ]
        removals = [["H10BO", "t0", "s3://w/a"], ["H10BO", "t0", "s3://w/b"]]
        rows = audit_orphan_cleanup(counts, removals)
        self.assertEqual(rows[0]["bytes_removed"], "200")
        self.assertEqual(rows[0]["objects_removed"], "2")

        with self.assertRaises(ValueError):
            audit_orphan_cleanup(counts, removals[:1])

    def test_apply_cost_reports_medians_over_repetitions(self) -> None:
        scenario = {
            "physical_order": "1",
            "scenario_id": "validation_001",
            "cells": "1",
            **{f"{treatment.lower()}_cells_evaluated": "1" for treatment in ("B0", "B1", "B2", "B3")},
            **{f"{treatment.lower()}_rows_written_logical": "1" for treatment in ("B0", "B1", "B2", "B3")},
        }
        timing = []
        storage = []
        for rep, seconds, delta in (("1", "1.0", 100), ("2", "2.0", 200), ("3", "9.0", 300)):
            for treatment in ("B0", "B1", "B2", "B3"):
                timing.append(
                    {
                        "repetition": rep,
                        "scenario_id": "validation_001",
                        "treatment_id": treatment,
                        "statement_index": "1",
                        "statement_label": "merge_revision",
                        "phase": "write",
                        "seconds": seconds,
                    }
                )
                timing.append(
                    {
                        "repetition": rep,
                        "scenario_id": "validation_001",
                        "treatment_id": treatment,
                        "statement_index": "2",
                        "statement_label": "expire_snapshots",
                        "phase": "maintenance",
                        "seconds": "0.5",
                    }
                )
                storage.append(
                    {
                        "repetition": rep,
                        "scenario_id": "validation_001",
                        "treatment_id": treatment,
                        "table": "t0",
                        "baseline_bytes": "1000",
                        "after_bytes": str(1000 + delta),
                        "delta_bytes": str(delta),
                        "baseline_data_bytes": "400",
                        "after_data_bytes": "440",
                        "after_snapshots": "1",
                    }
                )
        rows = aggregate_apply_cost(
            timing_rows=timing,
            storage_rows=storage,
            scenarios=[scenario],
            repetitions=3,
        )
        cost = next(row for row in rows if row["treatment_id"] == "B0")
        self.assertEqual(cost["write_seconds_median"], "2.000")
        self.assertEqual(cost["write_seconds_max"], "9.000")
        self.assertEqual(cost["maintenance_seconds_median"], "0.500")
        self.assertEqual(cost["delta_bytes_median"], "200")
        self.assertEqual(cost["delta_data_bytes_median"], "40")
        self.assertEqual(cost["delta_metadata_bytes_median"], "160")

    def test_footprint_rejects_a_size_that_differs_from_the_metadata(self) -> None:
        contract = _contract()
        contract["tables"] = {"B0": ["t0"], "B1": ["t1"], "B2": ["t2"], "B3": ["t3"]}
        contract["protocol"]["repetitions"] = 1
        footprint, states, listing = [], [], []
        for treatment, table in (("B0", "t0"), ("B1", "t1"), ("B2", "t2"), ("B3", "t3")):
            for phase in ("baseline", "after_revision"):
                path = f"s3://w/{table}/{phase}.parquet"
                footprint.append(
                    ["H10F", "1", "validation_001", phase, treatment, table, "data", path, "100", "14"]
                )
                states.append(["H10S", "1", "validation_001", phase, treatment, table, "1", "14"])
                listing.append(["H10L", "1", "validation_001", phase, treatment, table, path, "100"])
        rows = measure_phases(
            contract=contract,
            footprint_lines=footprint,
            state_lines=states,
            listing_lines=listing,
            scenarios=["validation_001"],
        )
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["delta_bytes"] == "0" for row in rows))

        drifted = [list(line) for line in listing]
        drifted[0][7] = "101"
        with self.assertRaises(ValueError):
            measure_phases(
                contract=contract,
                footprint_lines=footprint,
                state_lines=states,
                listing_lines=drifted,
                scenarios=["validation_001"],
            )


if __name__ == "__main__":
    unittest.main()
