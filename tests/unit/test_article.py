from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.article.pipeline import manifested_outputs, run_bundle


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run(output: Path, manifest_dir: Path | None = None) -> dict[str, object]:
    return run_bundle(
        tables_config=ROOT / "config/article/bundle_tables.csv",
        manifest_dir=manifest_dir or ROOT / "data/manifests",
        output_dir=output,
    )


class ArticleBundleTests(unittest.TestCase):
    def test_bundle_is_deterministic_and_matches_the_committed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data"
            first = _run(output)
            first_bytes = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
            second = _run(output)
            second_bytes = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["copied_tables"], 50)
            self.assertEqual(first["key_numbers"], 184)
            committed = ROOT / "papers/vintage_reconciliation/data"
            for relative, content in first_bytes.items():
                self.assertEqual((committed / relative).read_bytes(), content, str(relative))

    def test_key_numbers_reproduce_the_reported_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            numbers = {row["metric_id"]: row["value"] for row in _read_csv(output / "angka-kunci.csv")}
            expected = {
                "p1_confirmed_core_events": "96",
                "p1_confirmed_core_share": "0.7805",
                "p1_release_discrepancy_domains": "3",
                "p2_stable_cells": "14",
                "p3_recompute_ratio": "0.9048",
                "p3_b1_bytes_median": "190261",
                "p3_b3_store_bytes_median": "146352",
                "p4_b1_success_rate": "1.0000",
                "p4_b2_recalled_after_restart": "14",
                "b2_propagation_b2": "0.2857",
                "p3_sweep_panel_cells": "5378",
                "p3_b1_sweep_1_delta_bytes": "468313",
                "p3_b3_sweep_1_delta_bytes": "49262",
                "p3_b3_sweep_1_cells_evaluated": "1",
                "p3_b1_sweep_38_cells_evaluated": "5378",
                "p3_breakeven_b3_b1_byte": "none",
                "p4_b3_sweep_recall": "1.0000",
                "p4_b0_sweep_recall": "0.7660",
                "p3_real_value_revisions": "43",
                "p3_b1_real_releases_total_seconds": "15.050",
                "p3_b3_real_releases_total_seconds": "88.929",
                "p3_b0_release_2_write_seconds": "3.929",
                "p3_b1_release_2_write_seconds": "2.315",
                "p3_points_checked": "40",
                "p3_points_doubtful": "6",
                "p3_points_shifted": "2",
                "p3_largest_median_shift": "0.0901",
                "p4_b0_panel_recall": "0.7702",
                "p4_b3_panel_recall": "1.0000",
                "p4_b0_material_failures": "43",
                "p4_b2_superseded_serving_cells": "39",
                "p4_failure_cases": "125",
                "s2_b1_sweep_038_bytes_read": "3469013",
                "s2_b3_sweep_038_bytes_read": "5628612",
                "p3_plan_b0": "ReplaceData",
                "p3_plan_b3": "AppendData",
                "p3_b1_fixed_seconds": "10.1532",
                "p3_b3_bytes_per_cell": "78.8124",
                "p4_failure_serving_value_superseded": "39",
            }
            self.assertEqual({key: numbers[key] for key in expected}, expected)
            self.assertEqual(len(numbers), 184)
            for row in _read_csv(output / "angka-kunci.csv"):
                self.assertTrue((ROOT / row["source_file"]).exists(), row["source_file"])

    def test_bundle_rejects_a_source_that_drifted_from_its_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifests = Path(directory) / "manifests"
            shutil.copytree(ROOT / "data/manifests", manifests)
            path = manifests / "h9c-b3-lineage-audit.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            for item in manifest["outputs"]:
                if item["path"].endswith("h9c-reproducibility-table.csv"):
                    item["sha256"] = "0" * 64
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                _run(Path(directory) / "data", manifests)

    def test_stale_tables_are_removed_and_every_output_is_manifested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "p1-karakterisasi").mkdir(parents=True)
            (output / "p1-karakterisasi" / "old.csv").write_text("x\n1\n", encoding="utf-8")
            result = _run(output)
            self.assertEqual(result["removed_stale"], 1)
            self.assertFalse((output / "p1-karakterisasi" / "old.csv").exists())
            bundle = json.loads((output / "bundle-manifest.json").read_text(encoding="utf-8"))
            index = manifested_outputs(ROOT / "data/manifests")
            for table in bundle["copied_tables"]:
                self.assertEqual(index[table["source_path"]][0], table["sha256"])


if __name__ == "__main__":
    unittest.main()
