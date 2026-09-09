from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h5.pipeline import EVIDENCE_COLUMNS, run_h5


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path, evidence: Path | None = None) -> dict[str, object]:
    return run_h5(
        h4_manifest_path=ROOT / "data/manifests/h4-ingestion-classification.json",
        publication_manifest_path=ROOT / "data/manifests/h1-free-publications.json",
        evidence_path=evidence or ROOT / "config/h5/evidence_decisions.csv",
        events_output=output / "events.csv",
        traces_output=output / "traces.csv",
        gate_output=output / "gate.csv",
        manifest_output=output / "manifest.json",
    )


class H5GateTests(unittest.TestCase):
    def test_h5_is_deterministic_and_closes_gate_g1(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["event_rows"], 123)
            self.assertEqual(first["promoted_events"], 11)
            self.assertEqual(first["confirmed_core_events"], 96)
            self.assertEqual(first["confirmed_rate"], "0.7805")
            self.assertEqual(first["trace_count"], 14)
            self.assertEqual(first["trace_rows"], 38)
            self.assertEqual(first["gate_status"], "passed")

            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["gate_g1"]["criterion_2_confirmed_passed"])
            self.assertTrue(manifest["gate_g1"]["criterion_3_passed"])

    def test_promoted_vintage_traces_keep_old_old_new_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "traces.csv").open(newline="", encoding="utf-8") as handle:
                traces = list(csv.DictReader(handle))
            promoted = {}
            for row in traces:
                if row["trace_type"] == "provisional_to_revised_snapshot":
                    promoted.setdefault(row["trace_id"], []).append(row)
            self.assertEqual(len(promoted), 10)
            for rows in promoted.values():
                rows.sort(key=lambda row: int(row["vintage_order"]))
                self.assertEqual([row["vintage_order"] for row in rows], ["1", "2", "3"])
                self.assertEqual(rows[0]["value"], rows[1]["value"])
                self.assertNotEqual(rows[1]["value"], rows[2]["value"])
                self.assertEqual(
                    [row["source_id"] for row in rows],
                    ["bps_tpb_2024", "bps_tpb_2025", "bps_webapi"],
                )

    def test_uncorroborated_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            bad_evidence = output / "bad-evidence.csv"
            with (ROOT / "config/h5/evidence_decisions.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["corroborating_value"] = "999"
            with bad_evidence.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=EVIDENCE_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "does not corroborate"):
                _run(output, bad_evidence)


if __name__ == "__main__":
    unittest.main()

