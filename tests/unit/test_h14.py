from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kkciv_vintage.h14.pipeline import (
    audit_plans,
    audit_read_statistics,
    build_validation,
    normalise_plan,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("contracts/h14-plan-and-read-statistics.json")
TREATMENTS = ["B0", "B1", "B2", "B3"]


def setUpModule() -> None:
    os.chdir(ROOT)


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _line(rep: str, scenario: str, treatment: str, execution: str, iceberg: int, files: int) -> list[str]:
    return [
        "H14R",
        rep,
        scenario,
        treatment,
        execution,
        str(iceberg),
        str(files),
        "0",
        "4",
        "1",
        "100",
        "50",
        "MERGE INTO kkciv.sweep.b0_panel_current",
    ]


class ContractTest(unittest.TestCase):
    def test_frozen_contract_is_accepted(self) -> None:
        validate_contract(_contract())

    def test_an_instrumented_run_may_never_report_timing(self) -> None:
        contract = _contract()
        contract["measurement_boundary"]["timing"] = "measured_on_declared_environment"
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_the_event_log_is_the_source_of_the_statistics(self) -> None:
        contract = _contract()
        contract["instrumentation"]["event_log"]["enabled"] = False
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_one_repetition_cannot_show_the_statistics_are_stable(self) -> None:
        contract = _contract()
        contract["protocol"]["repetitions"] = 1
        with self.assertRaises(ValueError):
            validate_contract(contract)


class ReadStatisticsTest(unittest.TestCase):
    def _lines(self, *, second_rep_iceberg: int = 1000) -> list[list[str]]:
        lines = []
        for treatment in TREATMENTS:
            lines.append(_line("1", "sweep_001", treatment, "1", 1000, 500))
            lines.append(_line("2", "sweep_001", treatment, "1", second_rep_iceberg, 500))
        return lines

    def test_table_reads_and_staging_reads_are_kept_apart_and_summed(self) -> None:
        rows, summary = audit_read_statistics(
            self._lines(), repetitions=2, scenarios=["sweep_001"]
        )
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["iceberg_bytes_read"], "1000")
        self.assertEqual(rows[0]["file_bytes_read"], "500")
        self.assertEqual(rows[0]["bytes_read"], "1500")
        self.assertEqual({row["bytes_read"] for row in summary}, {"1500"})
        self.assertEqual({row["bytes_spread_ratio"] for row in summary}, {"0.000000"})
        self.assertEqual({row["repetitions_agreeing"] for row in summary}, {"2"})

    def test_a_size_that_drifts_beyond_the_tolerance_is_fatal(self) -> None:
        with self.assertRaises(ValueError):
            audit_read_statistics(
                self._lines(second_rep_iceberg=9999), repetitions=2, scenarios=["sweep_001"]
            )

    def test_a_size_that_drifts_inside_the_tolerance_is_reported_as_a_range(self) -> None:
        _, summary = audit_read_statistics(
            self._lines(second_rep_iceberg=1000 + 1), repetitions=2, scenarios=["sweep_001"]
        )
        self.assertEqual(summary[0]["iceberg_bytes_read_min"], "1000")
        self.assertEqual(summary[0]["iceberg_bytes_read_max"], "1001")
        self.assertLessEqual(float(summary[0]["bytes_spread_ratio"]), 0.001)

    def test_a_statement_that_reads_nothing_is_fatal(self) -> None:
        lines = [
            _line("1", "sweep_001", treatment, "1", 0, 0) for treatment in TREATMENTS
        ] + [_line("2", "sweep_001", treatment, "1", 0, 0) for treatment in TREATMENTS]
        with self.assertRaises(ValueError):
            audit_read_statistics(lines, repetitions=2, scenarios=["sweep_001"])

    def test_a_missing_repetition_is_fatal(self) -> None:
        lines = [_line("1", "sweep_001", treatment, "1", 1000, 500) for treatment in TREATMENTS]
        with self.assertRaises(ValueError):
            audit_read_statistics(lines, repetitions=2, scenarios=["sweep_001"])


class NormalisationTest(unittest.TestCase):
    def test_only_the_jvm_object_identity_is_normalised(self) -> None:
        first = "IcebergWrite org.apache.spark.Strategy$$Lambda$3770/0x000072862937d8a8@511b6a3 x"
        second = "IcebergWrite org.apache.spark.Strategy$$Lambda$3803/0x000079831138d0c8@722713da x"
        self.assertEqual(normalise_plan(first), normalise_plan(second))
        self.assertNotEqual(normalise_plan(first), normalise_plan(first + " ReplaceData"))


class PlanTest(unittest.TestCase):
    def _write_plans(self, directory: Path, *, same: bool) -> None:
        (directory / "plans").mkdir(parents=True)
        (directory / "logs").mkdir()
        (directory / "eventlogs").mkdir()
        for treatment in TREATMENTS:
            for rep in (1, 2):
                text = "== Physical Plan ==\nReplaceData (24)\n+- SortMergeJoin FullOuter (19)\n"
                if not same and rep == 2 and treatment == "B0":
                    text += "+- Exchange (3)\n"
                (directory / "plans" / f"rep{rep}-sweep_001-{treatment}.plan").write_text(text)
            (directory / "logs" / f"rep1-sweep_001-{treatment}.log").write_text("log\n")

    def test_a_plan_is_summarised_and_its_artifacts_are_inventoried(self) -> None:
        with TemporaryDirectory() as directory:
            raw = Path(directory)
            self._write_plans(raw, same=True)
            plans, artifacts = audit_plans(raw_dir=raw, repetitions=2, scenarios=["sweep_001"])
            self.assertEqual(len(plans), 4)
            self.assertEqual(plans[0]["top_operator"], "ReplaceData")
            self.assertEqual(plans[0]["copy_on_write_rewrite"], "yes")
            self.assertEqual(plans[0]["join_operators"], "SortMergeJoin")
            self.assertEqual(plans[0]["repetitions_agreeing"], "1")
            self.assertEqual({row["kind"] for row in artifacts}, {"plan", "session_log"})

    def test_a_plan_that_changed_between_repetitions_fails_the_audit(self) -> None:
        with TemporaryDirectory() as directory:
            raw = Path(directory)
            self._write_plans(raw, same=False)
            plans, artifacts = audit_plans(raw_dir=raw, repetitions=2, scenarios=["sweep_001"])
            rows = build_validation(
                contract=_contract(),
                environment={
                    "instrumentation": "event_log_enabled;timings_not_reported",
                    "host_nproc": "2",
                },
                read_rows=[],
                read_summary=[
                    {
                        "scenario_id": "sweep_001",
                        "treatment_id": treatment,
                        "bytes_read": "1500",
                        "bytes_spread_ratio": "0.000000",
                        "repetitions_agreeing": "2",
                    }
                    for treatment in TREATMENTS
                ],
                plans=plans,
                artifacts=artifacts,
            )
            self.assertIn("fail", {row["status"] for row in rows})


if __name__ == "__main__":
    unittest.main()
