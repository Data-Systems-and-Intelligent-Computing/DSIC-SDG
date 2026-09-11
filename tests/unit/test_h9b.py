from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path

from kkciv_vintage.h9b.pipeline import (
    run_h9b,
    select_single_source,
    synthetic_vintage_row,
    validate_contract,
    validate_human_decisions,
)


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run(output: Path) -> dict[str, object]:
    return run_h9b(
        contract_path=ROOT / "contracts/h9b-small-revision-execution.json",
        decisions_path=ROOT / "config/h9/human_decisions.csv",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        h6b_manifest_path=ROOT / "data/manifests/h6b-source-trust.json",
        h6c_manifest_path=ROOT / "data/manifests/h6c-cell-lineage.json",
        h8b_manifest_path=ROOT / "data/manifests/h8b-injected-revision-harness.json",
        b0_manifest_path=ROOT / "data/manifests/h7-b0-overwrite.json",
        b1_manifest_path=ROOT / "data/manifests/h8-b1-full-snapshot.json",
        b2_manifest_path=ROOT / "data/manifests/h7b-b2-single-source.json",
        b3_manifest_path=ROOT / "data/manifests/h9-b3-vintage-aware.json",
        routes_output=output / "routes.csv",
        states_output=output / "states.csv",
        recall_output=output / "recall.csv",
        synthetic_vintages_output=output / "synthetic-vintages.csv",
        validation_output=output / "validation.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


class H9BSmallRevisionExecutionTests(unittest.TestCase):
    def test_h9b_is_deterministic_and_executes_every_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["routes"], 20)
            self.assertEqual(first["payload_verified"], 20)
            self.assertEqual(first["injected_rows"], 28)
            self.assertEqual(first["b3_cells_recomputed"], 28)
            self.assertEqual(first["b1_rows_written"], 70)
            self.assertEqual(first["b0_revised_base_lost"], 28)
            self.assertEqual(first["b2_synthetic_served"], 8)
            self.assertEqual(first["b1_b3_unavailable"], 0)
            self.assertEqual(first["baseline_mismatches"], 0)

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["measurement"]["timing"], "not_measured")
            self.assertFalse(manifest["profile"]["final_experiment_freeze"])

    def test_treatment_effects_follow_their_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            routes = _read_csv(output / "routes.csv")
            by_treatment: dict[str, list[dict[str, str]]] = {}
            for row in routes:
                by_treatment.setdefault(row["treatment_id"], []).append(row)

            sizes = [int(row["input_rows"]) for row in by_treatment["B3"]]
            self.assertEqual(sizes, [1, 2, 4, 7, 14])
            self.assertEqual([int(row["cells_evaluated"]) for row in by_treatment["B3"]], sizes)
            self.assertEqual([int(row["rows_written_logical"]) for row in by_treatment["B3"]], [2 * n for n in sizes])
            self.assertEqual([row["rows_written_logical"] for row in by_treatment["B1"]], ["14"] * 5)
            self.assertEqual(
                [int(row["addressable_requests"]) for row in by_treatment["B1"]],
                [38 + n for n in sizes],
            )
            self.assertEqual([row["addressable_requests"] for row in by_treatment["B0"]], ["14"] * 5)
            self.assertEqual([row["revised_base_recalled"] for row in by_treatment["B0"]], ["0"] * 5)
            self.assertEqual([row["revised_base_recalled"] for row in by_treatment["B3"]], [str(n) for n in sizes])
            tpb_revisions = [
                int(dict(part.split("=") for part in row["revised_source_mix"].split(";")).get("bps_tpb_2025", "0"))
                for row in by_treatment["B2"]
            ]
            self.assertEqual([int(row["synthetic_observations_served"]) for row in by_treatment["B2"]], tpb_revisions)
            self.assertEqual({row["latest_vintage_cells"] for row in by_treatment["B2"]}, {"4"})
            self.assertEqual(
                Counter(row["single_revised_source"] for row in by_treatment["B0"]),
                Counter({"yes": 1, "no": 4}),
            )

    def test_synthetic_rows_are_later_and_never_official(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            vintages = _read_csv(output / "synthetic-vintages.csv")
            self.assertEqual({row["vintage_date"] for row in vintages}, {"2026-09-09"})
            self.assertEqual({row["retrieved_at"] for row in vintages}, {"2026-09-09T00:00:00+00:00"})
            self.assertEqual({row["source_id"] for row in vintages}, {"synthetic_revision_harness"})
            self.assertTrue(all("not BPS" in row["release_label"] for row in vintages))

        official = _read_csv(ROOT / "results/processed/h6-release-vintages.csv")
        row = synthetic_vintage_row(
            official,
            {"scenario_id": "x", "synthetic_vintage_id": "0" * 20},
            manifest_path="m",
            manifest_sha="s",
        )
        self.assertGreater(row["vintage_date"], max(item["vintage_date"] for item in official))

    def test_b2_scores_synthetic_rows_by_revised_source(self) -> None:
        vintages = [
            {"vintage_id": "old", "source_id": "high", "vintage_date": "2025-01-01"},
            {"vintage_id": "syn", "source_id": "synthetic_revision_harness", "vintage_date": "2026-09-09"},
        ]
        observations = [
            {"observation_id": "a", "cell_id": "c", "vintage_id": "old"},
            {"observation_id": "b", "cell_id": "c", "vintage_id": "syn"},
        ]
        scores = {"high": Decimal("0.9"), "low": Decimal("0.5")}
        low = select_single_source(vintages, observations, scores, {"b": "low"})
        high = select_single_source(vintages, observations, scores, {"b": "high"})
        self.assertEqual(low["c"]["observation_id"], "a")
        self.assertEqual(high["c"]["observation_id"], "b")
        with self.assertRaisesRegex(ValueError, "no frozen score"):
            select_single_source(vintages, observations, scores, {})

    def test_contract_and_decisions_reject_drift(self) -> None:
        contract = json.loads((ROOT / "contracts/h9b-small-revision-execution.json").read_text(encoding="utf-8"))
        changed = json.loads(json.dumps(contract))
        changed["synthetic_vintage"]["vintage_date_rule"] = "inherit_base_vintage_date"
        with self.assertRaisesRegex(ValueError, "approved rule"):
            validate_contract(changed)
        changed = json.loads(json.dumps(contract))
        changed["execution"]["timing"] = "measured"
        with self.assertRaisesRegex(ValueError, "timing"):
            validate_contract(changed)

        decisions = _read_csv(ROOT / "config/h9/human_decisions.csv")
        validate_human_decisions(decisions)
        decisions[3]["status"] = "proposed"
        with self.assertRaisesRegex(ValueError, "not approved"):
            validate_human_decisions(decisions)


if __name__ == "__main__":
    unittest.main()
