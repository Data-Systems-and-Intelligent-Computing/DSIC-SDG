from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from kkciv_vintage.h7c.pipeline import (
    BASE_EDGE_COLUMNS,
    BASE_NODE_COLUMNS,
    run_h7c,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run(output: Path, *, related_work: Path | None = None, pyproject: Path | None = None) -> dict[str, object]:
    return run_h7c(
        contract_path=ROOT / "contracts/h7c-evidence-lineage.json",
        literature_inventory_path=ROOT / "config/h7c/related_work_verification.csv",
        component_decisions_path=ROOT / "config/h7c/component_decisions.csv",
        related_work_path=related_work or ROOT / "docs/research/related-work.md",
        compose_path=ROOT / "docker-compose.yml",
        pyproject_path=pyproject or ROOT / "pyproject.toml",
        h6c_manifest_path=ROOT / "data/manifests/h6c-cell-lineage.json",
        h7_manifest_path=ROOT / "data/manifests/h7-b0-overwrite.json",
        h7b_manifest_path=ROOT / "data/manifests/h7b-b2-single-source.json",
        nodes_output=output / "nodes.csv",
        edges_output=output / "edges.csv",
        treatment_lineage_output=output / "treatment-lineage.csv",
        literature_output=output / "literature.csv",
        components_output=output / "components.csv",
        validation_output=output / "validation.csv",
        manifest_output=output / "manifest.json",
    )


class H7CEvidenceLineageTests(unittest.TestCase):
    def test_h7c_is_deterministic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["unique_sources"], 15)
            self.assertEqual(first["prior_occurrences"], 18)
            self.assertEqual(first["remaining_daftar"], 0)
            self.assertEqual(first["combined_nodes"], 207)
            self.assertEqual(first["combined_edges"], 491)
            self.assertEqual(first["treatment_paths"], 76)
            self.assertEqual(first["addressable_requests"], 28)
            self.assertEqual(first["non_addressable_requests"], 48)
            self.assertEqual(first["completeness_rate"], "1.0000")
            self.assertEqual(first["optional_components_not_used"], 4)

    def test_h6c_graph_identities_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            base_nodes = {
                row["node_id"]: row for row in _read_csv(ROOT / "results/processed/h6c-lineage-nodes.csv")
            }
            base_edges = {
                row["edge_id"]: row for row in _read_csv(ROOT / "results/processed/h6c-lineage-edges.csv")
            }
            extended_nodes = {row["node_id"]: row for row in _read_csv(output / "nodes.csv")}
            extended_edges = {row["edge_id"]: row for row in _read_csv(output / "edges.csv")}

            for node_id, base in base_nodes.items():
                self.assertEqual(
                    {column: extended_nodes[node_id][column] for column in BASE_NODE_COLUMNS},
                    base,
                )
            for edge_id, base in base_edges.items():
                self.assertEqual(
                    {column: extended_edges[edge_id][column] for column in BASE_EDGE_COLUMNS},
                    base,
                )

    def test_b0_and_b2_decisions_share_exact_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            rows = _read_csv(output / "treatment-lineage.csv")
            per_treatment = Counter(row["treatment_id"] for row in rows)
            addressable = Counter(
                row["treatment_id"] for row in rows if row["requested_addressable"] == "yes"
            )
            self.assertEqual(per_treatment, Counter({"B0": 38, "B2": 38}))
            self.assertEqual(addressable, Counter({"B0": 14, "B2": 14}))
            self.assertTrue(all(row["complete"] == "yes" for row in rows))
            self.assertEqual(len({row["treatment_lineage_id"] for row in rows}), 76)
            self.assertTrue(all(row["source_lineage_path_id"] for row in rows))
            self.assertTrue(all(row["treatment_output_node_id"] for row in rows))

    def test_unverified_related_work_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            related = root / "related-work.md"
            related.write_text(
                (ROOT / "docs/research/related-work.md").read_text(encoding="utf-8")
                + "\n| Unverified | Venue | 2026 | daftar |\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "retains 1 daftar"):
                _run(root / "output", related_work=related)

    def test_component_claim_must_match_repository_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pyproject = root / "pyproject.toml"
            pyproject.write_text(
                (ROOT / "pyproject.toml").read_text(encoding="utf-8")
                + "\ngeopandas = 'unexpected'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Python dependencies"):
                _run(root / "output", pyproject=pyproject)

    def test_contract_rejects_fuzzy_matching(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h7c-evidence-lineage.json").read_text(encoding="utf-8")
        )
        contract["lineage_extension"]["fuzzy_matching_allowed"] = True
        with self.assertRaisesRegex(ValueError, "must not use fuzzy"):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
