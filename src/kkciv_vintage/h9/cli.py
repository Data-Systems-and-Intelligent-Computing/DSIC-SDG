from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h9


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H9 track A B3 vintage-aware treatment")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h9-b3-vintage-aware.json"))
    parser.add_argument("--ddl", type=Path, default=Path("infra/spark/h9-b3.sql"))
    parser.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    parser.add_argument("--h6c-manifest", type=Path, default=Path("data/manifests/h6c-cell-lineage.json"))
    parser.add_argument("--b0-manifest", type=Path, default=Path("data/manifests/h7-b0-overwrite.json"))
    parser.add_argument("--b1-manifest", type=Path, default=Path("data/manifests/h8-b1-full-snapshot.json"))
    parser.add_argument("--arrival-output", type=Path, default=Path("results/processed/h9-b3-arrival-catalog.csv"))
    parser.add_argument("--store-output", type=Path, default=Path("results/processed/h9-b3-observation-store.csv"))
    parser.add_argument("--impact-output", type=Path, default=Path("results/processed/h9-b3-impact.csv"))
    parser.add_argument("--current-state-output", type=Path, default=Path("results/processed/h9-b3-current-state.csv"))
    parser.add_argument("--asof-output", type=Path, default=Path("results/processed/h9-b3-asof-states.csv"))
    parser.add_argument("--reproducibility-output", type=Path, default=Path("results/processed/h9-b3-reproducibility.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h9-b3-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h9-b3-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h9-b3-vintage-aware.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h9(
        contract_path=args.contract,
        ddl_path=args.ddl,
        h6_manifest_path=args.h6_manifest,
        h6c_manifest_path=args.h6c_manifest,
        b0_manifest_path=args.b0_manifest,
        b1_manifest_path=args.b1_manifest,
        arrival_output=args.arrival_output,
        store_output=args.store_output,
        impact_output=args.impact_output,
        current_state_output=args.current_state_output,
        asof_output=args.asof_output,
        reproducibility_output=args.reproducibility_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H9 {result['treatment_id']} stored {result['store_rows']} vintage rows and serves "
        f"{result['final_rows']} cells after {result['arrival_batches']} arrivals"
    )
    print(
        f"Recomputed cells={result['recomputed_cells']}/{result['full_recompute_cells']} "
        f"(ratio {result['recompute_ratio']}); vintage reads={result['reproduction_successes']}/"
        f"{result['input_rows']}; implementation={result['status']}"
    )
    print(
        f"H9_LOGIC|{result['store_rows']}|{result['final_rows']}|{result['arrival_batches']}|"
        f"{result['recomputed_cells']}|{result['full_recompute_cells']}|"
        f"{result['reproduction_successes']}|{result['reproduction_failures']}|"
        f"{result['asof_rows']}|{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
