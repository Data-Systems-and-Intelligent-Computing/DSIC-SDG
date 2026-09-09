from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from kkciv_vintage.h4.pipeline import (
    CORE_CAUSES,
    build_ingestion,
    classify_events,
    load_domains,
    load_rules,
    run_h4,
)


ROOT = Path(__file__).resolve().parents[2]


class ManifestIngestionTests(unittest.TestCase):
    def test_non_finite_observation_is_rejected(self) -> None:
        columns = [
            "source_id",
            "indicator_key",
            "series_key",
            "release_date",
            "observed_period",
            "geo_level",
            "geo_code",
            "geo_name",
            "unit",
            "value",
            "producer",
            "methodology_version",
            "source_record_id",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerow(
                    {
                        "source_id": "test",
                        "indicator_key": "x",
                        "series_key": "total",
                        "release_date": "2026-01-01",
                        "observed_period": "2025",
                        "geo_level": "national",
                        "geo_code": "9999",
                        "geo_name": "Indonesia",
                        "unit": "percent",
                        "value": "NaN",
                        "producer": "test",
                        "methodology_version": "test",
                        "source_record_id": "1",
                    }
                )
            with self.assertRaisesRegex(ValueError, "non-finite"):
                build_ingestion(
                    datasets=[("test", path)],
                    domains={"x": "education"},
                    batch_id="test-batch",
                )

    def test_full_h4_run_is_deterministic_and_manifested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            kwargs = {
                "baseline_manifest_path": ROOT / "data/manifests/h3-comparison.json",
                "release_manifest_path": ROOT
                / "data/manifests/h3-release-reconciliation.json",
                "rules_path": ROOT / "config/h4/classification_rules.csv",
                "domains_path": ROOT / "config/h4/indicator_domains.csv",
                "ingestion_output": output / "ingestion.csv",
                "inventory_output": output / "inventory.csv",
                "events_output": output / "events.csv",
                "summary_output": output / "summary.csv",
                "manifest_output": output / "manifest.json",
            }
            first = run_h4(**kwargs)
            first_bytes = {
                path.name: path.read_bytes() for path in output.iterdir()
            }
            second = run_h4(**kwargs)
            second_bytes = {
                path.name: path.read_bytes() for path in output.iterdir()
            }

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["ingestion_rows"], 7666)
            self.assertEqual(first["event_rows"], 123)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["gate_g1"]["criterion_2_candidate_inclusive_passed"])
            self.assertFalse(manifest["gate_g1"]["criterion_2_confirmed_passed"])


class SharedClassificationTests(unittest.TestCase):
    def test_rules_cover_all_current_event_labels_and_domains(self) -> None:
        rules = load_rules(ROOT / "config/h4/classification_rules.csv")
        domains = load_domains(ROOT / "config/h4/indicator_domains.csv")
        events = classify_events(
            baseline_discrepancies=ROOT / "results/processed/h3-discrepancies.csv",
            release_discrepancies=ROOT
            / "results/processed/h3-release-discrepancies.csv",
            granularity_path=ROOT / "results/processed/h3-granularity.csv",
            domains=domains,
            rules=rules,
        )
        self.assertEqual(len(events), 123)
        self.assertEqual(
            {row["domain"] for row in events},
            {"education", "environment", "energy", "economy", "ecology"},
        )
        self.assertFalse(
            {row["cause_family"] for row in events}
            - CORE_CAUSES
            - {"rounding_or_presentation"}
        )

    def test_dated_publication_change_has_stronger_evidence_than_webapi_gap(self) -> None:
        events = classify_events(
            baseline_discrepancies=ROOT / "results/processed/h3-discrepancies.csv",
            release_discrepancies=ROOT
            / "results/processed/h3-release-discrepancies.csv",
            granularity_path=ROOT / "results/processed/h3-granularity.csv",
            domains=load_domains(ROOT / "config/h4/indicator_domains.csv"),
            rules=load_rules(ROOT / "config/h4/classification_rules.csv"),
        )
        renewable = {
            row["observed_period"]: row
            for row in events
            if row["event_kind"] == "release_value_difference"
            and row["indicator_key"] == "sdg07_renewable_share"
        }
        self.assertEqual(renewable["2023"]["classification"], "vintage_observed")
        self.assertEqual(renewable["2023"]["evidence_level"], "observed")
        self.assertEqual(renewable["2019"]["classification"], "vintage_candidate")
        self.assertEqual(renewable["2019"]["evidence_level"], "candidate")


if __name__ == "__main__":
    unittest.main()
