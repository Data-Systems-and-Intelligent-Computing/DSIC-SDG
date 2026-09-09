from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H7 B0 overwrite baseline")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h7-b0-overwrite.json"))
    parser.add_argument("--ddl", type=Path, default=Path("infra/spark/h7-b0.sql"))
    parser.add_argument(
        "--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json")
    )
    parser.add_argument(
        "--operations-output",
        type=Path,
        default=Path("results/processed/h7-b0-operations.csv"),
    )
    parser.add_argument(
        "--state-output",
        type=Path,
        default=Path("results/processed/h7-b0-final-state.csv"),
    )
    parser.add_argument(
        "--reproducibility-output",
        type=Path,
        default=Path("results/processed/h7-b0-reproducibility.csv"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/processed/h7-b0-summary.csv"),
    )
    parser.add_argument(
        "--manifest-output", type=Path, default=Path("data/manifests/h7-b0-overwrite.json")
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h7(
        contract_path=args.contract,
        ddl_path=args.ddl,
        h6_manifest_path=args.h6_manifest,
        operations_output=args.operations_output,
        state_output=args.state_output,
        reproducibility_output=args.reproducibility_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H7 {result['treatment_id']} applied {result['input_rows']} rows in "
        f"{result['vintage_batches']} vintage batches; final state={result['final_rows']} rows"
    )
    print(
        f"Overwritten vintages={result['overwritten_rows']}; historical read failures="
        f"{result['reproduction_failures']}; implementation={result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
