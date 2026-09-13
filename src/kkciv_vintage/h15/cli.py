from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h15


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H15 tracks A and C: manuscript tables and figure data"
    )
    parser.add_argument("--contract", type=Path, default=Path("contracts/h15-result-tables-and-figures.json"))
    parser.add_argument("--manifest-dir", type=Path, default=Path("data/manifests"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/processed"))
    parser.add_argument(
        "--table-inventory-output", type=Path, default=Path("results/processed/h15-table-inventory.csv")
    )
    parser.add_argument(
        "--figure-inventory-output", type=Path, default=Path("results/processed/h15-figure-inventory.csv")
    )
    parser.add_argument("--figure-data-output", type=Path, default=Path("results/processed/h15-figure-data.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h15-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h15-summary.csv"))
    parser.add_argument(
        "--manifest-output", type=Path, default=Path("data/manifests/h15-result-tables-and-figures.json")
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h15(
        contract_path=args.contract,
        manifest_dir=args.manifest_dir,
        output_dir=args.output_dir,
        table_inventory_output=args.table_inventory_output,
        figure_inventory_output=args.figure_inventory_output,
        figure_data_output=args.figure_data_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H15 composed {result['tables']} tables ({result['added_tables']} added after the frame was "
        f"frozen) and {result['figures']} figures with {result['figure_points']} points, from "
        f"{result['verified_sources']} checksum-verified sources"
    )
    print(
        "H15_VERIFY|"
        + "|".join(
            [
                str(result["tables"]),
                str(result["added_tables"]),
                str(result["figures"]),
                str(result["figure_points"]),
                str(result["verified_sources"]),
                result["status"],
            ]
        )
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
