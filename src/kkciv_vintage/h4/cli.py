from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H4 manifest ingestion and shared classification rules"
    )
    parser.add_argument(
        "--baseline-manifest",
        type=Path,
        default=Path("data/manifests/h3-comparison.json"),
    )
    parser.add_argument(
        "--release-manifest",
        type=Path,
        default=Path("data/manifests/h3-release-reconciliation.json"),
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=Path("config/h4/classification_rules.csv"),
    )
    parser.add_argument(
        "--domains",
        type=Path,
        default=Path("config/h4/indicator_domains.csv"),
    )
    parser.add_argument(
        "--ingestion-output",
        type=Path,
        default=Path("results/processed/h4-ingested-observations.csv"),
    )
    parser.add_argument(
        "--inventory-output",
        type=Path,
        default=Path("results/processed/h4-ingestion-inventory.csv"),
    )
    parser.add_argument(
        "--events-output",
        type=Path,
        default=Path("results/processed/h4-classified-events.csv"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/processed/h4-classification-summary.csv"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h4-ingestion-classification.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h4(
        baseline_manifest_path=args.baseline_manifest,
        release_manifest_path=args.release_manifest,
        rules_path=args.rules,
        domains_path=args.domains,
        ingestion_output=args.ingestion_output,
        inventory_output=args.inventory_output,
        events_output=args.events_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H4 batch {result['batch_id']} ingested {result['ingestion_rows']} observations "
        f"and classified {result['event_rows']} events"
    )
    print(
        "G1 criterion 2 rates: "
        f"candidate-inclusive={result['candidate_rate']}, "
        f"confirmed={result['confirmed_rate']}; "
        f"gate={result['gate_status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
