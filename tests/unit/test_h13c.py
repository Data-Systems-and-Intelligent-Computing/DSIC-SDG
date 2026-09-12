from __future__ import annotations

import csv
import json
import os
import unittest
from decimal import Decimal
from pathlib import Path

from kkciv_vintage.h13c.pipeline import (
    audit_panel,
    cross_check_physical,
    validate_contract,
    validate_procedure,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("contracts/h13c-reproducibility-audit.json")
STEPS = Path("config/h8c/reproducibility_audit_steps.csv")
PROCESSED = Path("results/processed")


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

    def test_an_unclassified_failure_may_not_be_allowed(self) -> None:
        contract = _contract()
        contract["failure_classification"]["unclassified_allowed"] = True
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_synthetic_requests_stay_out_of_the_p4_audit(self) -> None:
        contract = _contract()
        contract["scope"]["synthetic_requests"] = "the injected revisions are audited here too"
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_the_frozen_procedure_must_keep_its_ten_steps(self) -> None:
        steps = _read_csv(STEPS)
        validate_procedure(steps, 10)
        with self.assertRaises(ValueError):
            validate_procedure(steps[:-1], 10)


class AuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vintages = [
            {
                "vintage_id": "v1",
                "source_id": "pub_2024",
                "source_channel": "publication_pdf",
                "vintage_date": "2024-12-31",
                "vintage_basis": "published_release",
                "retrieved_at": "2026-01-01T00:00:00+00:00",
                "release_label": "pub 2024",
                "source_manifest_path": "data/manifests/example.json",
                "source_manifest_sha256": "a" * 64,
            },
            {
                "vintage_id": "v2",
                "source_id": "webapi",
                "source_channel": "webapi",
                "vintage_date": "2026-09-08",
                "vintage_basis": "retrieval_snapshot",
                "retrieved_at": "2026-09-08T00:00:00+00:00",
                "release_label": "webapi",
                "source_manifest_path": "data/manifests/example.json",
                "source_manifest_sha256": "b" * 64,
            },
        ]
        self.scores = [
            {
                "rank": "1",
                "source_id": "pub_2024",
                "trust_score": "0.962500",
                "vintage_id": "v1",
                "vintage_date": "2024-12-31",
            },
            {
                "rank": "2",
                "source_id": "webapi",
                "trust_score": "0.907143",
                "vintage_id": "v2",
                "vintage_date": "2026-09-08",
            },
        ]

    def _observation(self, cell: str, vintage: str, value: str, record: str) -> dict[str, str]:
        return {
            "observation_id": f"{cell}-{vintage}",
            "cell_id": cell,
            "vintage_id": vintage,
            "domain": "economy",
            "indicator_key": "sdg08_example",
            "series_key": "total",
            "observed_period": "2023",
            "period_granularity": "year",
            "geo_level": "province",
            "geo_code": "3200",
            "geo_name": "Contoh",
            "unit": "percent",
            "value_decimal": f"{Decimal(value):.10f}",
            "value_lexeme": value,
            "published_decimal_places": "2",
            "producer": "Badan Pusat Statistik",
            "methodology_version": "example",
            "source_artifact_path": f"data/raw/{vintage}.json",
            "source_artifact_sha256": ("c" if vintage == "v1" else "d") * 64,
            "source_record_id": record,
            "ingestion_batch_id": "batch",
            "transformation_run_id": "run",
            "transformation_version": "v1",
            "trace_id": "",
            "cause_family": "",
            "evidence_level": "official_panel",
        }

    def test_a_revised_value_lost_by_overwrite_is_material_while_a_duplicate_is_not(self) -> None:
        observations = [
            self._observation("cell_revised", "v1", "10.00", "r1"),
            self._observation("cell_revised", "v2", "10.50", "r2"),
            self._observation("cell_same", "v1", "20.00", "r3"),
            self._observation("cell_same", "v2", "20.00", "r4"),
        ]
        audited = audit_panel(
            vintages=self.vintages,
            observations=observations,
            scores=self.scores,
            selection_contract_version="b2.1",
            selection_run_id="test",
        )
        panel = {row["treatment_id"]: row for row in audited["table"]}
        self.assertEqual(panel["B0"]["failures"], "2")
        self.assertEqual(panel["B0"]["success_rate"], "0.5000")
        self.assertEqual(panel["B1"]["failures"], "0")
        self.assertEqual(panel["B3"]["failures"], "0")
        b0_material = sum(
            int(row["material_failures"])
            for row in audited["profile"]
            if row["treatment_id"] == "B0" and row["failure_kind"] == "overwritten_by_later_vintage"
        )
        self.assertEqual(b0_material, 1)
        lost = [
            row
            for row in audited["cases"]
            if row["treatment_id"] == "B0" and row["failure_kind"] == "overwritten_by_later_vintage"
        ]
        self.assertEqual(len(lost), 1)
        self.assertEqual(lost[0]["lost_value_lexeme"], "10.00")
        self.assertEqual(lost[0]["served_value_lexeme"], "10.50")
        self.assertTrue(lost[0]["lost_source_record_id"])

    def test_a_treatment_serving_a_superseded_value_is_reported_as_its_own_kind(self) -> None:
        observations = [
            self._observation("cell_revised", "v1", "10.00", "r1"),
            self._observation("cell_revised", "v2", "10.50", "r2"),
        ]
        audited = audit_panel(
            vintages=self.vintages,
            observations=observations,
            scores=self.scores,
            selection_contract_version="b2.1",
            selection_run_id="test",
        )
        superseded = [row for row in audited["cases"] if row["failure_kind"] == "serving_value_superseded"]
        self.assertEqual([row["treatment_id"] for row in superseded], ["B2"])
        self.assertEqual(superseded[0]["served_value_lexeme"], "10.00")
        self.assertEqual(superseded[0]["lost_value_lexeme"], "10.50")

    def test_b1_and_b3_answer_every_request(self) -> None:
        observations = [
            self._observation("cell_revised", "v1", "10.00", "r1"),
            self._observation("cell_revised", "v2", "10.50", "r2"),
        ]
        audited = audit_panel(
            vintages=self.vintages,
            observations=observations,
            scores=self.scores,
            selection_contract_version="b2.1",
            selection_run_id="test",
        )
        panel = {row["treatment_id"]: row for row in audited["table"]}
        for treatment in ("B1", "B3"):
            self.assertEqual(panel[treatment]["success_rate"], "1.0000")
        self.assertEqual(panel["B1"]["historical_snapshot_successes"], "1")
        self.assertEqual(panel["B3"]["historical_vintage_key_successes"], "1")
        self.assertEqual(audited["lineage"]["completeness"], "1.0000")


class CrossCheckTest(unittest.TestCase):
    def test_a_derived_count_that_the_sweep_contradicts_is_fatal(self) -> None:
        table = [
            {"treatment_id": "B0", "requests": "6983", "failures": "1605"},
            {"treatment_id": "B1", "requests": "6983", "failures": "0"},
            {"treatment_id": "B2", "requests": "6983", "failures": "1605"},
            {"treatment_id": "B3", "requests": "6983", "failures": "0"},
        ]
        scenarios = [{"scenario_id": "sweep_001", "cells_revised": "1"}]
        good = [
            {"scenario_id": "sweep_001", "treatment_id": "B0", "request_kind": "official", "addressable": "5377"},
            {"scenario_id": "sweep_001", "treatment_id": "B1", "request_kind": "official", "addressable": "6983"},
        ]
        self.assertEqual(len(cross_check_physical(table=table, recall_rows=good, scenarios=scenarios)), 2)
        bad = [
            {"scenario_id": "sweep_001", "treatment_id": "B0", "request_kind": "official", "addressable": "5378"}
        ]
        with self.assertRaises(ValueError):
            cross_check_physical(table=table, recall_rows=bad, scenarios=scenarios)

    def test_the_committed_audit_matches_the_committed_sweep(self) -> None:
        table = [row for row in _read_csv(PROCESSED / "h13c-reproducibility-table.csv") if row["scale"] == "panel"]
        checks = cross_check_physical(
            table=table,
            recall_rows=_read_csv(PROCESSED / "h11-recall.csv"),
            scenarios=_read_csv(PROCESSED / "h11-sweep-scenarios.csv"),
        )
        self.assertEqual(len(checks), 24)


if __name__ == "__main__":
    unittest.main()
