from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from kkciv_vintage.h7c.pipeline import BASE_EDGE_COLUMNS, BASE_NODE_COLUMNS
from kkciv_vintage.h9c.pipeline import audit_impact, run_h9c, validate_contract


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run(output: Path, procedure: Path | None = None) -> dict[str, object]:
    return run_h9c(
        contract_path=ROOT / "contracts/h9c-b3-lineage-audit.json",
        procedure_path=procedure or ROOT / "config/h8c/reproducibility_audit_steps.csv",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        h6c_manifest_path=ROOT / "data/manifests/h6c-cell-lineage.json",
        h8c_manifest_path=ROOT / "data/manifests/h8c-reproducibility-lineage.json",
        h9_manifest_path=ROOT / "data/manifests/h9-b3-vintage-aware.json",
        audit_output=output / "audit.csv",
        impact_audit_output=output / "impact.csv",
        metrics_output=output / "metrics.csv",
        table_output=output / "table.csv",
        figure_output=output / "figure.csv",
        nodes_output=output / "nodes.csv",
        edges_output=output / "edges.csv",
        closure_output=output / "closure.csv",
        validation_output=output / "validation.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


class H9CB3LineageAuditTests(unittest.TestCase):
    def test_h9c_is_deterministic_and_closes_four_treatments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["base_nodes"], 294)
            self.assertEqual(first["base_edges"], 810)
            self.assertEqual(first["closed_nodes"], 377)
            self.assertEqual(first["closed_edges"], 1088)
            self.assertEqual(first["audit_requests"], 152)
            self.assertEqual(first["addressable"], 104)
            self.assertEqual(first["unavailable"], 48)
            self.assertEqual(first["b3_addressable"], 38)
            self.assertEqual(first["impact_mismatches"], 0)
            self.assertEqual(first["completeness"], "1.0000")

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["scope"]["treatments"], ["B0", "B1", "B2", "B3"])
            self.assertFalse(manifest["presentation"]["manuscript_figure_claimed"])

    def test_metrics_keep_inherited_results_and_add_b3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            metrics = {row["treatment_id"]: row for row in _read_csv(output / "metrics.csv")}
            audit = _read_csv(output / "audit.csv")
            inherited = _read_csv(ROOT / "results/processed/h8c-reproducibility-audit.csv")

            self.assertEqual(
                {
                    treatment: (
                        row["serving_state_successes"],
                        row["historical_snapshot_successes"],
                        row["historical_vintage_key_successes"],
                        row["failures"],
                        row["success_rate"],
                    )
                    for treatment, row in metrics.items()
                },
                {
                    "B0": ("14", "0", "0", "24", "0.3684"),
                    "B1": ("14", "24", "0", "0", "1.0000"),
                    "B2": ("14", "0", "0", "24", "0.3684"),
                    "B3": ("14", "0", "24", "0", "1.0000"),
                },
            )
            self.assertEqual(audit[: len(inherited)], inherited)
            b3 = [row for row in audit if row["treatment_id"] == "B3"]
            self.assertEqual(len(b3), 38)
            self.assertEqual(
                {row["requested_observation_id"] for row in b3},
                {row["requested_observation_id"] for row in inherited if row["treatment_id"] == "B0"},
            )
            self.assertTrue(all(row["identity_match"] == row["decimal_match"] == row["lexeme_match"] == "yes" for row in b3))
            self.assertEqual(Counter(row["access_class"] for row in b3), Counter({"vintage_key": 24, "serving_state": 14}))

    def test_h8c_graph_is_immutable_and_b3_arrivals_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            base_nodes = {row["node_id"]: row for row in _read_csv(ROOT / "results/processed/h8c-lineage-nodes.csv")}
            base_edges = {row["edge_id"]: row for row in _read_csv(ROOT / "results/processed/h8c-lineage-edges.csv")}
            nodes = {row["node_id"]: row for row in _read_csv(output / "nodes.csv")}
            edges = {row["edge_id"]: row for row in _read_csv(output / "edges.csv")}

            for node_id, base in base_nodes.items():
                self.assertEqual({column: nodes[node_id][column] for column in BASE_NODE_COLUMNS}, {column: base[column] for column in BASE_NODE_COLUMNS})
            for edge_id, base in base_edges.items():
                self.assertEqual({column: edges[edge_id][column] for column in BASE_EDGE_COLUMNS}, {column: base[column] for column in BASE_EDGE_COLUMNS})
            node_types = Counter(row["node_type"] for row in nodes.values())
            relationships = Counter(row["relationship"] for row in edges.values())
            self.assertEqual(node_types["arrival_batch"], 3)
            self.assertEqual(node_types["reproducibility_metric"], 4)
            self.assertEqual(node_types["evidence_table"], 2)
            self.assertEqual(relationships["arrival_recomputes_cell"], 38)
            self.assertEqual(relationships["audit_decision_contributes_to_metric"], 152)

            closure = _read_csv(output / "closure.csv")
            self.assertEqual(len(closure), 152)
            self.assertEqual(len({row["closure_id"] for row in closure}), 152)
            self.assertEqual(len({row["evidence_table_node_id"] for row in closure}), 1)
            for row in closure:
                self.assertEqual(row["complete"], "yes")
                self.assertEqual(bool(row["arrival_batch_node_id"]), row["treatment_id"] == "B3")
                self.assertEqual(bool(row["snapshot_state_node_ids"]), row["treatment_id"] == "B1")

    def test_impact_audit_rejects_a_missed_dirty_cell(self) -> None:
        graph_nodes = _read_csv(ROOT / "results/processed/h8c-lineage-nodes.csv")
        graph_edges = _read_csv(ROOT / "results/processed/h8c-lineage-edges.csv")
        observations = _read_csv(ROOT / "results/processed/h6-indicator-observations.csv")
        impact = _read_csv(ROOT / "results/processed/h9-b3-impact.csv")
        store = _read_csv(ROOT / "results/processed/h9-b3-observation-store.csv")
        arrivals = _read_csv(ROOT / "results/processed/h9-b3-arrival-catalog.csv")
        current = _read_csv(ROOT / "results/processed/h9-b3-current-state.csv")

        rows = audit_impact(graph_nodes=graph_nodes, graph_edges=graph_edges, observations=observations, impact_rows=impact, store=store, arrivals=arrivals, current=current)
        self.assertEqual(len(rows), 38)

        stale = [dict(row) for row in current]
        stale[0]["recomputed_at_arrival"] = "1"
        with self.assertRaisesRegex(ValueError, "last dirty arrival"):
            audit_impact(graph_nodes=graph_nodes, graph_edges=graph_edges, observations=observations, impact_rows=impact, store=store, arrivals=arrivals, current=stale)

        undercount = [dict(row) for row in arrivals]
        undercount[2]["dirty_cells"] = "9"
        with self.assertRaisesRegex(ValueError, "dirty cells disagree"):
            audit_impact(graph_nodes=graph_nodes, graph_edges=graph_edges, observations=observations, impact_rows=impact, store=store, arrivals=undercount, current=current)

    def test_contract_and_procedure_guard_the_audit(self) -> None:
        contract = json.loads((ROOT / "contracts/h9c-b3-lineage-audit.json").read_text(encoding="utf-8"))
        changed = json.loads(json.dumps(contract))
        changed["expected_results"]["B3"]["failures"] = 1
        with self.assertRaisesRegex(ValueError, "expected treatment outcomes"):
            validate_contract(changed)
        changed = json.loads(json.dumps(contract))
        changed["presentation"]["manuscript_figure_claimed"] = True
        with self.assertRaisesRegex(ValueError, "rendered manuscript figure"):
            validate_contract(changed)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            procedure = output / "procedure.csv"
            procedure.write_text(
                (ROOT / "config/h8c/reproducibility_audit_steps.csv").read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "frozen by H8C"):
                _run(output, procedure)


if __name__ == "__main__":
    unittest.main()
