from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H8 track A B1 full-snapshot treatment")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h8-b1-full-snapshot.json"))
    parser.add_argument("--ddl", type=Path, default=Path("infra/spark/h8-b1.sql"))
    parser.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    parser.add_argument("--b0-manifest", type=Path, default=Path("data/manifests/h7-b0-overwrite.json"))
    parser.add_argument("--catalog-output", type=Path, default=Path("results/processed/h8-b1-snapshot-catalog.csv"))
    parser.add_argument("--snapshot-states-output", type=Path, default=Path("results/processed/h8-b1-snapshot-states.csv"))
    parser.add_argument("--current-state-output", type=Path, default=Path("results/processed/h8-b1-current-state.csv"))
    parser.add_argument("--reproducibility-output", type=Path, default=Path("results/processed/h8-b1-reproducibility.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h8-b1-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h8-b1-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h8-b1-full-snapshot.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h8(
        contract_path=args.contract,
        ddl_path=args.ddl,
        h6_manifest_path=args.h6_manifest,
        b0_manifest_path=args.b0_manifest,
        catalog_output=args.catalog_output,
        snapshot_states_output=args.snapshot_states_output,
        current_state_output=args.current_state_output,
        reproducibility_output=args.reproducibility_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H8 {result['treatment_id']} materialized {result['snapshot_count']} complete "
        f"snapshots ({result['logical_full_copy_rows']} row appearances)"
    )
    print(
        f"Historical reads={result['reproduction_successes']}/{result['input_rows']}; "
        f"failures={result['reproduction_failures']}; implementation={result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
