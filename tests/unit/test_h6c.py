from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from kkciv_vintage.h6c.pipeline import run_h6c, validate_contract


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path) -> dict[str, object]:
    return run_h6c(
        contract_path=ROOT / "contracts/h6c-cell-lineage.json",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        nodes_output=output / "nodes.csv",
        edges_output=output / "edges.csv",
        paths_output=output / "paths.csv",
        validation_output=output / "validation.csv",
        manifest_output=output / "manifest.json",
    )


class H6CCellLineageTests(unittest.TestCase):
    def test_h6c_is_deterministic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["node_count"], 101)
            self.assertEqual(first["edge_count"], 235)
            self.assertEqual(first["path_count"], 38)
            self.assertEqual(first["cell_count"], 14)
            self.assertEqual(first["source_record_count"], 38)
            self.assertEqual(first["raw_locator_collision_groups"], 4)
            self.assertEqual(first["raw_locator_collision_observations"], 20)
            self.assertEqual(first["completeness_rate"], "1.0000")

    def test_every_cell_reaches_each_exact_source_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "paths.csv").open(newline="", encoding="utf-8") as handle:
                paths = list(csv.DictReader(handle))
            with (output / "nodes.csv").open(newline="", encoding="utf-8") as handle:
                nodes = list(csv.DictReader(handle))

            self.assertEqual(len({row["lineage_path_id"] for row in paths}), 38)
            self.assertEqual(len({row["source_record_node_id"] for row in paths}), 38)
            self.assertTrue(all(row["complete"] == "yes" for row in paths))
            self.assertTrue(all(row["core_hop_count"] == "4" for row in paths))
            per_cell = Counter(row["cell_id"] for row in paths)
            self.assertEqual(Counter(per_cell.values()), Counter({3: 10, 2: 4}))
            node_types = Counter(row["node_type"] for row in nodes)
            self.assertEqual(node_types["indicator_cell"], 14)
            self.assertEqual(node_types["source_record"], 38)
            self.assertEqual(node_types["source_artifact"], 3)
            self.assertEqual(node_types["source_manifest"], 2)

    def test_reused_raw_locators_are_disclosed_and_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "paths.csv").open(newline="", encoding="utf-8") as handle:
                paths = list(csv.DictReader(handle))
            affected = [row for row in paths if int(row["raw_locator_occurrences"]) > 1]
            self.assertEqual(len(affected), 20)
            self.assertEqual(
                {row["raw_locator_occurrences"] for row in affected}, {"4", "6"}
            )
            self.assertTrue(
                all(row["source_record_resolution"] == "composite_with_cell_coordinates" for row in affected)
            )

    def test_contract_rejects_fuzzy_matching(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h6c-cell-lineage.json").read_text(encoding="utf-8")
        )
        contract["resolution"]["fuzzy_matching_allowed"] = True
        with self.assertRaisesRegex(ValueError, "must not use fuzzy"):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
