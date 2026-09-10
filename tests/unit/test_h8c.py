from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from kkciv_vintage.h7c.pipeline import BASE_EDGE_COLUMNS, BASE_NODE_COLUMNS
from kkciv_vintage.h8c.pipeline import run_h8c, validate_contract, validate_procedure


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run(output: Path) -> dict[str, object]:
    return run_h8c(
        contract_path=ROOT / "contracts/h8c-reproducibility-lineage.json",
        procedure_path=ROOT / "config/h8c/reproducibility_audit_steps.csv",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        h6c_manifest_path=ROOT / "data/manifests/h6c-cell-lineage.json",
        h7c_manifest_path=ROOT / "data/manifests/h7c-evidence-lineage.json",
        b0_manifest_path=ROOT / "data/manifests/h7-b0-overwrite.json",
        b1_manifest_path=ROOT / "data/manifests/h8-b1-full-snapshot.json",
        b2_manifest_path=ROOT / "data/manifests/h7b-b2-single-source.json",
        h8b_manifest_path=ROOT / "data/manifests/h8b-injected-revision-harness.json",
        audit_output=output / "audit.csv",
        metrics_output=output / "metrics.csv",
        table_output=output / "table.csv",
        figure_output=output / "figure.csv",
        nodes_output=output / "nodes.csv",
        edges_output=output / "edges.csv",
        closure_output=output / "closure.csv",
        procedure_output=output / "procedure.csv",
        validation_output=output / "validation.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


class H8CReproducibilityLineageTests(unittest.TestCase):
    def test_h8c_is_deterministic_and_closes_implemented_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["base_nodes"], 207)
            self.assertEqual(first["base_edges"], 491)
            self.assertEqual(first["closed_nodes"], 294)
            self.assertEqual(first["closed_edges"], 810)
            self.assertEqual(first["audit_requests"], 114)
            self.assertEqual(first["addressable"], 66)
            self.assertEqual(first["unavailable"], 48)
            self.assertEqual(first["completeness"], "1.0000")

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["scope"]["implemented_treatments"], ["B0", "B1", "B2"])
            self.assertEqual(manifest["scope"]["deferred_treatment"], "B3")
            self.assertFalse(manifest["presentation"]["manuscript_figure_claimed"])

    def test_metrics_reconcile_after_exact_row_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            metrics = {row["treatment_id"]: row for row in _read_csv(output / "metrics.csv")}
            audit = _read_csv(output / "audit.csv")

            self.assertEqual(
                {
                    treatment: (
                        row["serving_state_successes"],
                        row["historical_snapshot_successes"],
                        row["failures"],
                        row["success_rate"],
                    )
                    for treatment, row in metrics.items()
                },
                {
                    "B0": ("14", "0", "24", "0.3684"),
                    "B1": ("14", "24", "0", "1.0000"),
                    "B2": ("14", "0", "24", "0.3684"),
                },
            )
            self.assertEqual(Counter(row["treatment_id"] for row in audit), Counter({"B0": 38, "B1": 38, "B2": 38}))
            self.assertTrue(all(row["audit_status"] == "passed" for row in audit))
            successful = [row for row in audit if row["computed_addressable"] == "yes"]
            self.assertEqual(len(successful), 66)
            self.assertTrue(
                all(
                    row["identity_match"] == row["decimal_match"] == row["lexeme_match"] == "yes"
                    for row in successful
                )
            )

    def test_h7c_graph_is_immutable_and_b1_snapshots_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            base_nodes = {row["node_id"]: row for row in _read_csv(ROOT / "results/processed/h7c-lineage-nodes.csv")}
            base_edges = {row["edge_id"]: row for row in _read_csv(ROOT / "results/processed/h7c-lineage-edges.csv")}
            nodes = {row["node_id"]: row for row in _read_csv(output / "nodes.csv")}
            edges = {row["edge_id"]: row for row in _read_csv(output / "edges.csv")}

            for node_id, base in base_nodes.items():
                self.assertEqual({column: nodes[node_id][column] for column in BASE_NODE_COLUMNS}, {column: base[column] for column in BASE_NODE_COLUMNS})
            for edge_id, base in base_edges.items():
                self.assertEqual({column: edges[edge_id][column] for column in BASE_EDGE_COLUMNS}, {column: base[column] for column in BASE_EDGE_COLUMNS})
            node_types = Counter(row["node_type"] for row in nodes.values())
            relationships = Counter(row["relationship"] for row in edges.values())
            self.assertEqual(node_types["snapshot_state"], 3)
            self.assertEqual(node_types["reproducibility_metric"], 3)
            self.assertEqual(node_types["evidence_table"], 1)
            self.assertEqual(node_types["figure_input"], 1)
            self.assertEqual(relationships["output_available_in_snapshot"], 42)
            self.assertEqual(relationships["audit_decision_contributes_to_metric"], 114)

    def test_every_closure_reaches_metric_table_figure_and_procedure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            closure = _read_csv(output / "closure.csv")
            self.assertEqual(len(closure), 114)
            self.assertEqual(len({row["closure_id"] for row in closure}), 114)
            self.assertTrue(all(row["complete"] == "yes" for row in closure))
            for row in closure:
                self.assertTrue(row["source_lineage_path_id"])
                self.assertTrue(row["reproducibility_metric_node_id"])
                self.assertTrue(row["evidence_table_node_id"])
                self.assertTrue(row["figure_input_node_id"])
                self.assertTrue(row["audit_procedure_node_id"])
                self.assertEqual(bool(row["snapshot_state_node_ids"]), row["treatment_id"] == "B1")

    def test_contract_and_procedure_reject_b3_overclaim_and_step_reordering(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h8c-reproducibility-lineage.json").read_text(encoding="utf-8")
        )
        contract["scope"]["implemented_treatments"].append("B3")
        with self.assertRaisesRegex(ValueError, "explicitly deferring B3"):
            validate_contract(contract)

        contract = json.loads(
            (ROOT / "contracts/h8c-reproducibility-lineage.json").read_text(encoding="utf-8")
        )
        procedure = _read_csv(ROOT / "config/h8c/reproducibility_audit_steps.csv")
        procedure[0]["step_order"] = "2"
        with self.assertRaisesRegex(ValueError, "contiguous and ordered"):
            validate_procedure(procedure, contract)


if __name__ == "__main__":
    unittest.main()
