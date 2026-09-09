from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h6b


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H6 Jalur B source-trust score")
    parser.add_argument(
        "--contract", type=Path, default=Path("contracts/h6b-source-trust.json")
    )
    parser.add_argument(
        "--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json")
    )
    parser.add_argument(
        "--source-registry", type=Path, default=Path("config/sources/bps_sources.csv")
    )
    parser.add_argument(
        "--scores-output",
        type=Path,
        default=Path("results/processed/h6b-source-trust-scores.csv"),
    )
    parser.add_argument(
        "--selection-output",
        type=Path,
        default=Path("results/processed/h6b-selection-preview.csv"),
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        default=Path("results/processed/h6b-source-trust-validation.csv"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h6b-source-trust.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h6b(
        contract_path=args.contract,
        h6_manifest_path=args.h6_manifest,
        source_registry_path=args.source_registry,
        scores_output=args.scores_output,
        selection_output=args.selection_output,
        validation_output=args.validation_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H6B froze {result['source_count']} source scores over "
        f"{result['cell_count']} H6 cells"
    )
    print(
        f"Preview selected latest vintage for {result['latest_selected']} cells and "
        f"an older vintage for {result['older_selected']} cells; status={result['status']}"
    )
    print(
        f"H6B_VERIFY|{result['source_count']}|{result['cell_count']}|"
        f"{result['latest_selected']}|{result['older_selected']}|"
        f"{result['selected_value_differs']}|{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
