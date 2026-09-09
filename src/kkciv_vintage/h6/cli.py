from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H6 explicit-vintage schema validation"
    )
    parser.add_argument("--contract", type=Path, default=Path("contracts/h6-vintage-schema.json"))
    parser.add_argument("--ddl", type=Path, default=Path("infra/spark/h6-vintage-schema.sql"))
    parser.add_argument("--h5-manifest", type=Path, default=Path("data/manifests/h5-gate1.json"))
    parser.add_argument(
        "--publication-manifest",
        type=Path,
        default=Path("data/manifests/h1-free-publications.json"),
    )
    parser.add_argument(
        "--webapi-manifest",
        type=Path,
        default=Path("data/manifests/h1-free-webapi-data.json"),
    )
    parser.add_argument(
        "--vintages-output",
        type=Path,
        default=Path("results/processed/h6-release-vintages.csv"),
    )
    parser.add_argument(
        "--observations-output",
        type=Path,
        default=Path("results/processed/h6-indicator-observations.csv"),
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        default=Path("results/processed/h6-schema-validation.csv"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h6-vintage-schema.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h6(
        contract_path=args.contract,
        ddl_path=args.ddl,
        h5_manifest_path=args.h5_manifest,
        publication_manifest_path=args.publication_manifest,
        webapi_manifest_path=args.webapi_manifest,
        vintages_output=args.vintages_output,
        observations_output=args.observations_output,
        validation_output=args.validation_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H6 schema {result['contract_version']} projected {result['observation_rows']} "
        f"observations across {result['vintage_rows']} explicit vintages and "
        f"{result['cell_count']} stable cells"
    )
    print(f"Schema validation={result['status']}; manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
