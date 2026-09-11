from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h9b


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H9 track B small-revision harness execution")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h9b-small-revision-execution.json"))
    parser.add_argument("--decisions", type=Path, default=Path("config/h9/human_decisions.csv"))
    parser.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    parser.add_argument("--h6b-manifest", type=Path, default=Path("data/manifests/h6b-source-trust.json"))
    parser.add_argument("--h6c-manifest", type=Path, default=Path("data/manifests/h6c-cell-lineage.json"))
    parser.add_argument("--h8b-manifest", type=Path, default=Path("data/manifests/h8b-injected-revision-harness.json"))
    parser.add_argument("--b0-manifest", type=Path, default=Path("data/manifests/h7-b0-overwrite.json"))
    parser.add_argument("--b1-manifest", type=Path, default=Path("data/manifests/h8-b1-full-snapshot.json"))
    parser.add_argument("--b2-manifest", type=Path, default=Path("data/manifests/h7b-b2-single-source.json"))
    parser.add_argument("--b3-manifest", type=Path, default=Path("data/manifests/h9-b3-vintage-aware.json"))
    parser.add_argument("--routes-output", type=Path, default=Path("results/processed/h9b-route-executions.csv"))
    parser.add_argument("--states-output", type=Path, default=Path("results/processed/h9b-post-revision-states.csv"))
    parser.add_argument("--recall-output", type=Path, default=Path("results/processed/h9b-recall-audit.csv"))
    parser.add_argument("--synthetic-vintages-output", type=Path, default=Path("results/processed/h9b-synthetic-vintages.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h9b-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h9b-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h9b-small-revision-execution.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h9b(
        contract_path=args.contract,
        decisions_path=args.decisions,
        h6_manifest_path=args.h6_manifest,
        h6b_manifest_path=args.h6b_manifest,
        h6c_manifest_path=args.h6c_manifest,
        h8b_manifest_path=args.h8b_manifest,
        b0_manifest_path=args.b0_manifest,
        b1_manifest_path=args.b1_manifest,
        b2_manifest_path=args.b2_manifest,
        b3_manifest_path=args.b3_manifest,
        routes_output=args.routes_output,
        states_output=args.states_output,
        recall_output=args.recall_output,
        synthetic_vintages_output=args.synthetic_vintages_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H9B executed {result['routes']} routes over {result['scenarios']} scenarios logically; "
        f"payload verified={result['payload_verified']}, injected rows={result['injected_rows']}"
    )
    print(
        f"B3 recomputed {result['b3_cells_recomputed']} cells; B1 wrote {result['b1_rows_written']} rows; "
        f"B0 lost {result['b0_revised_base_lost']} revised values; B2 served {result['b2_synthetic_served']} revisions"
    )
    print(
        f"H9B_VERIFY|{result['scenarios']}|{result['routes']}|{result['payload_verified']}|"
        f"{result['payload_mismatches']}|{result['injected_rows']}|{result['b3_cells_recomputed']}|"
        f"{result['b1_rows_written']}|{result['b0_revised_base_lost']}|{result['b2_synthetic_served']}|"
        f"{result['b1_b3_unavailable']}|{result['baseline_mismatches']}|{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
