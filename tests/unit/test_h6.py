from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h6.pipeline import run_h6, validate_contract, validate_ddl


ROOT = Path(__file__).resolve().parents[2]


def _run(output: Path) -> dict[str, object]:
    return run_h6(
        contract_path=ROOT / "contracts/h6-vintage-schema.json",
        ddl_path=ROOT / "infra/spark/h6-vintage-schema.sql",
        h5_manifest_path=ROOT / "data/manifests/h5-gate1.json",
        publication_manifest_path=ROOT / "data/manifests/h1-free-publications.json",
        webapi_manifest_path=ROOT / "data/manifests/h1-free-webapi-data.json",
        vintages_output=output / "vintages.csv",
        observations_output=output / "observations.csv",
        validation_output=output / "validation.csv",
        manifest_output=output / "manifest.json",
    )


class H6SchemaTests(unittest.TestCase):
    def test_h6_is_deterministic_and_lossless(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = _run(output)
            first_bytes = {path.name: path.read_bytes() for path in output.iterdir()}
            second = _run(output)
            second_bytes = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["contract_version"], "h6.1")
            self.assertEqual(first["vintage_rows"], 3)
            self.assertEqual(first["observation_rows"], 38)
            self.assertEqual(first["cell_count"], 14)
            self.assertEqual(first["status"], "validated")

            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["fixture"]["lossless_projection"])

    def test_cell_identity_is_stable_across_vintages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _run(output)
            with (output / "observations.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            by_trace: dict[str, list[dict[str, str]]] = {}
            for row in rows:
                by_trace.setdefault(row["trace_id"], []).append(row)
            self.assertEqual(len(by_trace), 14)
            for trace_rows in by_trace.values():
                self.assertEqual(len({row["cell_id"] for row in trace_rows}), 1)
                self.assertEqual(len({row["vintage_id"] for row in trace_rows}), len(trace_rows))
                for row in trace_rows:
                    self.assertEqual(
                        row["published_decimal_places"],
                        str(len(row["value_lexeme"].partition(".")[2])),
                    )

    def test_contract_rejects_source_dependent_cell_identity(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h6-vintage-schema.json").read_text(encoding="utf-8")
        )
        contract["identity"]["cell_id_fields"].append("source_id")
        with self.assertRaisesRegex(ValueError, "independent of source"):
            validate_contract(contract)

    def test_ddl_matches_the_machine_readable_contract(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/h6-vintage-schema.json").read_text(encoding="utf-8")
        )
        ddl = (ROOT / "infra/spark/h6-vintage-schema.sql").read_text(encoding="utf-8")
        validate_ddl(contract, ddl)
        with self.assertRaisesRegex(ValueError, "value_lexeme"):
            validate_ddl(contract, ddl.replace("value_lexeme STRING NOT NULL", "value_lexeme INT"))


if __name__ == "__main__":
    unittest.main()
