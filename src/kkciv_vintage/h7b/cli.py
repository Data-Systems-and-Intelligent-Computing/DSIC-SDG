from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h7b


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H7 Jalur B B2 implementation")
    parser.add_argument(
        "--contract", type=Path, default=Path("contracts/h7b-b2-single-source.json")
    )
    parser.add_argument("--ddl", type=Path, default=Path("infra/spark/h7b-b2.sql"))
    parser.add_argument(
        "--h6b-manifest", type=Path, default=Path("data/manifests/h6b-source-trust.json")
    )
    parser.add_argument(
        "--state-output",
        type=Path,
        default=Path("results/processed/h7b-b2-selected-state.csv"),
    )
    parser.add_argument(
        "--discarded-output",
        type=Path,
        default=Path("results/processed/h7b-b2-discarded-candidates.csv"),
    )
    parser.add_argument(
        "--reproducibility-output",
        type=Path,
        default=Path("results/processed/h7b-b2-reproducibility.csv"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/processed/h7b-b2-summary.csv"),
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        default=Path("results/processed/h7b-b2-validation.csv"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h7b-b2-single-source.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h7b(
        contract_path=args.contract,
        ddl_path=args.ddl,
        h6b_manifest_path=args.h6b_manifest,
        state_output=args.state_output,
        discarded_output=args.discarded_output,
        reproducibility_output=args.reproducibility_output,
        summary_output=args.summary_output,
        validation_output=args.validation_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H7B {result['treatment_id']} selected {result['selected_rows']} of "
        f"{result['input_rows']} candidates across {result['cell_count']} cells"
    )
    print(
        f"Discarded={result['discarded_rows']}; older selections={result['older_selected']}; "
        f"historical read failures={result['reproduction_failures']}; status={result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
