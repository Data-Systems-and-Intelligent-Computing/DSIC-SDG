from __future__ import annotations

import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h6.pipeline import OBSERVATION_COLUMNS
from kkciv_vintage.h9.pipeline import (
    RESOLUTION_COLUMNS,
    run_h9,
    simulate_vintage_aware,
    validate_contract,
    validate_ddl,
)


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _fixture() -> tuple[list[dict[str, str]], ...]:
    return (
        _read_csv(ROOT / "results/processed/h6-release-vintages.csv"),
        _read_csv(ROOT / "results/processed/h6-indicator-observations.csv"),
        _read_csv(ROOT / "results/processed/h6c-lineage-nodes.csv"),
        _read_csv(ROOT / "results/processed/h6c-lineage-edges.csv"),
    )


def _run(output: Path) -> dict[str, object]:
    return run_h9(
        contract_path=ROOT / "contracts/h9-b3-vintage-aware.json",
        ddl_path=ROOT / "infra/spark/h9-b3.sql",
        h6_manifest_path=ROOT / "data/manifests/h6-vintage-schema.json",
        h6c_manifest_path=ROOT / "data/manifests/h6c-cell-lineage.json",
        b0_manifest_path=ROOT / "data/manifests/h7-b0-overwrite.json",
        b1_manifest_path=ROOT / "data/manifests/h8-b1-full-snapshot.json",
        arrival_output=output / "arrivals.csv",
        store_output=output / "store.csv",
        impact_output=output / "impact.csv",
        current_state_output=output / "current.csv",
        asof_output=output / "asof.csv",
        reproducibility_output=output / "reproducibility.csv",
        validation_output=output / "validation.csv",
        summary_output=output / "summary.csv",
        manifest_output=output / "manifest.json",
    )


class H9B3VintageAwareTests(unittest.TestCase):
    def test_h9_is_deterministic_and_recalls_every_vintage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["store_rows"], 38)
            self.assertEqual(first["final_rows"], 14)
            self.assertEqual(first["arrival_batches"], 3)
            self.assertEqual(first["recomputed_cells"], 38)
            self.assertEqual(first["full_recompute_cells"], 42)
            self.assertEqual(first["untouched_cells"], 4)
            self.assertEqual(first["recompute_ratio"], "0.9048")
            self.assertEqual(first["asof_rows"], 42)
            self.assertEqual(first["logical_materialized_rows"], 52)
            self.assertEqual(first["reproduction_successes"], 38)
            self.assertEqual(first["reproduction_failures"], 0)

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["reproducibility"]["depends_on_table_snapshots"])
            self.assertEqual(manifest["measurement"]["physical_bytes_and_runtime"], "deferred_to_H10")
            self.assertEqual(manifest["injected_workload"]["h8b_route_status"], "prepared_not_run")

    def test_only_lineage_dirty_cells_are_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            arrivals = _read_csv(output / "arrivals.csv")
            impact = _read_csv(output / "impact.csv")
            current = _read_csv(output / "current.csv")

            self.assertEqual([row["dirty_cells"] for row in arrivals], ["14", "14", "10"])
            self.assertEqual([row["untouched_cells"] for row in arrivals], ["0", "0", "4"])
            self.assertEqual([row["value_changed_cells"] for row in arrivals], ["0", "4", "10"])
            self.assertEqual([row["provenance_only_cells"] for row in arrivals], ["0", "10", "0"])
            self.assertTrue(all(row["incremental_equals_full"] == "yes" for row in arrivals))
            self.assertEqual(len(impact), 38)
            self.assertTrue(all(row["lineage_edge_id"].startswith("edge:") for row in impact))
            recomputed_at = sorted(row["recomputed_at_arrival"] for row in current)
            self.assertEqual(recomputed_at, ["2"] * 4 + ["3"] * 10)
            self.assertEqual(sum(int(row["value_revision_count"]) for row in current), 14)

    def test_resolution_is_independent_of_arrival_order(self) -> None:
        vintages, observations, nodes, edges = _fixture()
        in_order = simulate_vintage_aware(vintages, observations, nodes, edges)
        newest_first = sorted(vintages, key=lambda row: row["vintage_date"], reverse=True)
        shuffled = simulate_vintage_aware(
            vintages,
            observations,
            nodes,
            edges,
            arrival_vintage_ids=[row["vintage_id"] for row in newest_first],
        )

        def project(rows: list[dict[str, str]], columns: list[str]) -> list[tuple[str, ...]]:
            return sorted(tuple(row[column] for column in columns) for row in rows)

        self.assertEqual(project(in_order[3], RESOLUTION_COLUMNS), project(shuffled[3], RESOLUTION_COLUMNS))
        self.assertEqual(
            project(in_order[4], [*OBSERVATION_COLUMNS, "asof_order"]),
            project(shuffled[4], [*OBSERVATION_COLUMNS, "asof_order"]),
        )
        late_arrivals = shuffled[0][1:]
        self.assertTrue(all(int(row["unchanged_resolution_cells"]) > 0 for row in late_arrivals))
        self.assertTrue(all(row["resolved_changed_cells"] == "0" for row in late_arrivals))
        self.assertEqual(shuffled[6]["reproduction_successes"], 38)

    def test_dirty_cells_require_matching_lineage(self) -> None:
        vintages, observations, nodes, edges = _fixture()
        cell_nodes = [row["node_id"] for row in nodes if row["node_type"] == "indicator_cell"]
        tampered = [dict(row) for row in edges]
        target = next(row for row in tampered if row["relationship"] == "observation_materializes_cell")
        target["to_node_id"] = next(node for node in cell_nodes if node != target["to_node_id"])
        with self.assertRaisesRegex(ValueError, "different cell"):
            simulate_vintage_aware(vintages, observations, nodes, tampered)

        missing = [row for row in edges if row["edge_id"] != target["edge_id"]]
        with self.assertRaisesRegex(ValueError, "no H6C lineage edge"):
            simulate_vintage_aware(vintages, observations, nodes, missing)

    def test_store_is_append_only_in_contract_ddl_and_apply_script(self) -> None:
        contract = json.loads((ROOT / "contracts/h9-b3-vintage-aware.json").read_text(encoding="utf-8"))
        ddl = (ROOT / "infra/spark/h9-b3.sql").read_text(encoding="utf-8")
        validate_ddl(contract, ddl)
        with self.assertRaisesRegex(ValueError, "append-only"):
            validate_ddl(contract, ddl + "\nDELETE FROM kkciv.experiments.b3_observation_vintages;")
        with self.assertRaisesRegex(ValueError, "value_decimal"):
            validate_ddl(contract, ddl.replace("value_decimal DECIMAL(38,10)", "value_decimal DOUBLE", 1))

        changed = json.loads(json.dumps(contract))
        changed["store"]["mutation_policy"] = "merge_latest"
        with self.assertRaisesRegex(ValueError, "append-only"):
            validate_contract(changed)
        changed = json.loads(json.dumps(contract))
        changed["reproducibility"]["depends_on_table_snapshots"] = True
        with self.assertRaisesRegex(ValueError, "table snapshots"):
            validate_contract(changed)

        script = " ".join((ROOT / "scripts/h9_apply.sh").read_text(encoding="utf-8").split())
        for statement in ("UPDATE", "DELETE FROM", "MERGE INTO", "INSERT OVERWRITE"):
            self.assertIsNone(re.search(rf"{statement} \$\{{store_table\}}", script), statement)
        self.assertIn("INSERT INTO ${store_table}", script)
        self.assertIn("MERGE INTO ${serving_table}", script)


if __name__ == "__main__":
    unittest.main()
