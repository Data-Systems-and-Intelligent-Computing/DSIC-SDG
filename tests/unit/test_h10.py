from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h10.pipeline import (
    audit_recall,
    measure_footprint,
    run_h10,
    validate_contract,
    validate_human_decisions,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "results/raw/h10/h10a-20260911"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _contract() -> dict[str, object]:
    return json.loads((ROOT / "contracts/h10-storage-recall.json").read_text(encoding="utf-8"))


def _run(output: Path) -> dict[str, object]:
    return run_h10(
        contract_path=ROOT / "contracts/h10-storage-recall.json",
        decisions_path=ROOT / "config/h10/human_decisions.csv",
        raw_dir=RAW_DIR,
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        b1_manifest_path=ROOT / "data/manifests/h8-b1-full-snapshot.json",
        h9c_manifest_path=ROOT / "data/manifests/h9c-b3-lineage-audit.json",
        files_output=output / "objects.csv",
        footprint_output=output / "footprint.csv",
        tables_output=output / "tables.csv",
        treatment_summary_output=output / "by-treatment.csv",
        recall_output=output / "recall.csv",
        validation_output=output / "validation.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


def _single_table_contract() -> dict[str, object]:
    contract = _contract()
    contract["tables"] = {"B0": ["t0"], "B1": ["t1"], "B2": ["t2"], "B3": ["t3"]}
    contract["protocol"]["repetitions"] = 1
    return contract


def _synthetic_lines(size: str = "100") -> tuple[list[list[str]], list[list[str]], list[list[str]]]:
    footprint, states, listing = [], [], []
    for treatment, table in (("B0", "t0"), ("B1", "t1"), ("B2", "t2"), ("B3", "t3")):
        base = f"s3://w/{table}"
        footprint += [
            ["H10F", "1", treatment, table, "data", f"{base}/data/a.parquet", size, "14"],
            ["H10F", "1", treatment, table, "manifest", f"{base}/metadata/m.avro", "50", ""],
            ["H10F", "1", treatment, table, "manifest_list", f"{base}/metadata/snap.avro", "", ""],
            ["H10F", "1", treatment, table, "metadata_json", f"{base}/metadata/00000.metadata.json", "", ""],
        ]
        states.append(["H10S", "1", treatment, table, "1", "14"])
        listing += [
            ["H10L", "1", treatment, table, f"{base}/data/a.parquet", "100"],
            ["H10L", "1", treatment, table, f"{base}/metadata/m.avro", "50"],
            ["H10L", "1", treatment, table, f"{base}/metadata/snap.avro", "30"],
            ["H10L", "1", treatment, table, f"{base}/metadata/00000.metadata.json", "20"],
            ["H10L", "1", treatment, table, f"{base}/data/orphan.parquet", "999"],
        ]
    return footprint, states, listing


class H10StorageRecallTests(unittest.TestCase):
    def test_h10_is_deterministic_and_recalls_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["repetitions"], 3)
            self.assertEqual(
                (first["b0_recalled"], first["b1_recalled"], first["b2_recalled"], first["b3_recalled"]),
                (14, 38, 14, 38),
            )
            by_treatment = {row["treatment_id"]: row for row in _read_csv(output / "by-treatment.csv")}
            self.assertEqual(by_treatment["B1"]["physical_rows"], "42")
            self.assertEqual(by_treatment["B3"]["physical_rows"], "52")
            self.assertEqual(by_treatment["B0"]["physical_rows"], "14")
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["measurement"]["timing"], "not_measured")

    def test_footprint_counts_reachable_objects_and_excludes_orphans(self) -> None:
        footprint, states, listing = _synthetic_lines()
        files, per_class, tables, summary = measure_footprint(
            contract=_single_table_contract(), footprint_lines=footprint, state_lines=states, listing_lines=listing
        )
        self.assertEqual(len(files), 16)
        table = next(row for row in tables if row["table"] == "t0")
        self.assertEqual(table["reachable_bytes"], "200")
        self.assertEqual(table["unreferenced_bytes"], "999")
        self.assertEqual({row["total_bytes_median"] for row in summary}, {"200"})

    def test_footprint_rejects_missing_objects_and_size_drift(self) -> None:
        footprint, states, listing = _synthetic_lines(size="101")
        with self.assertRaisesRegex(ValueError, "size differs"):
            measure_footprint(contract=_single_table_contract(), footprint_lines=footprint, state_lines=states, listing_lines=listing)
        footprint, states, listing = _synthetic_lines()
        listing = [row for row in listing if not row[4].endswith("snap.avro")]
        with self.assertRaisesRegex(ValueError, "missing object"):
            measure_footprint(contract=_single_table_contract(), footprint_lines=footprint, state_lines=states, listing_lines=listing)

    def test_recall_rejects_wrong_values_and_unexpected_availability(self) -> None:
        observations = [{"observation_id": "o1", "value_lexeme": "1.00"}]
        audit = [{"treatment_id": t, "requested_observation_id": "o1", "computed_addressable": "yes"} for t in ("B0", "B1", "B2", "B3")]
        reproducibility = [{"requested_observation_id": "o1", "matching_snapshot_orders": "1"}]
        contract = _contract()
        contract["recall_after_restart"]["expected_addressable"] = {"B0": 1, "B1": 1, "B2": 1, "B3": 1}
        good = [
            ["H10R", "B0", "o1", "o1", "1.00", "current"],
            ["H10R", "B1", "o1", "o1", "1.00", "snapshot_orders=1"],
            ["H10R", "B2", "o1", "o1", "1.00", "current"],
            ["H10R", "B3", "o1", "o1", "1.00", "vintage_key"],
        ]
        rows = audit_recall(recall_lines=good, observations=observations, h9c_audit=audit, b1_reproducibility=reproducibility, contract=contract)
        self.assertEqual(len(rows), 4)
        wrong_value = [list(row) for row in good]
        wrong_value[3][4] = "1.01"
        with self.assertRaisesRegex(ValueError, "different value"):
            audit_recall(recall_lines=wrong_value, observations=observations, h9c_audit=audit, b1_reproducibility=reproducibility, contract=contract)
        missing = [list(row) for row in good]
        missing[1][3] = missing[1][4] = ""
        with self.assertRaisesRegex(ValueError, "disagrees with the H9C audit"):
            audit_recall(recall_lines=missing, observations=observations, h9c_audit=audit, b1_reproducibility=reproducibility, contract=contract)

    def test_contract_and_decisions_guard_the_protocol(self) -> None:
        contract = _contract()
        contract["measurement_boundary"]["timing"] = "measured"
        with self.assertRaisesRegex(ValueError, "runtime"):
            validate_contract(contract)
        contract = _contract()
        contract["protocol"]["repetitions"] = 1
        with self.assertRaisesRegex(ValueError, "three repetitions"):
            validate_contract(contract)
        decisions = _read_csv(ROOT / "config/h10/human_decisions.csv")
        validate_human_decisions(decisions)
        decisions[0]["status"] = "proposed"
        with self.assertRaisesRegex(ValueError, "not approved"):
            validate_human_decisions(decisions)


if __name__ == "__main__":
    unittest.main()
