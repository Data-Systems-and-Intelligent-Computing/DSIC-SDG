from __future__ import annotations

import argparse
from pathlib import Path

from kkciv_vintage.h11.pipeline import TREATMENTS

from .pipeline import run_h13c


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H13 track C panel reproducibility audit and failure analysis"
    )
    parser.add_argument("--contract", type=Path, default=Path("contracts/h13c-reproducibility-audit.json"))
    parser.add_argument("--steps", type=Path, default=Path("config/h8c/reproducibility_audit_steps.csv"))
    parser.add_argument(
        "--panel-manifest", type=Path, default=Path("data/manifests/h11-main-sweep-payload.json")
    )
    parser.add_argument(
        "--h9c-table", type=Path, default=Path("results/processed/h9c-reproducibility-table.csv")
    )
    parser.add_argument("--recall", type=Path, default=Path("results/processed/h11-recall.csv"))
    parser.add_argument("--scores", type=Path, default=Path("results/processed/h6b-source-trust-scores.csv"))
    parser.add_argument("--b2-contract", type=Path, default=Path("contracts/h7b-b2-single-source.json"))
    parser.add_argument(
        "--table-output", type=Path, default=Path("results/processed/h13c-reproducibility-table.csv")
    )
    parser.add_argument(
        "--profile-output", type=Path, default=Path("results/processed/h13c-failure-profile.csv")
    )
    parser.add_argument("--cases-output", type=Path, default=Path("results/processed/h13c-failure-cases.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h13c-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h13c-summary.csv"))
    parser.add_argument(
        "--manifest-output", type=Path, default=Path("data/manifests/h13c-reproducibility-audit.json")
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h13c(
        contract_path=args.contract,
        steps_path=args.steps,
        panel_manifest_path=args.panel_manifest,
        h9c_table_path=args.h9c_table,
        recall_path=args.recall,
        scores_path=args.scores,
        b2_contract_path=args.b2_contract,
        table_output=args.table_output,
        profile_output=args.profile_output,
        cases_output=args.cases_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H13C audited {result['requests']} published figures against all four treatments, "
        f"cross-checked on {result['cross_checks']} measured scenario-treatment pairs"
    )
    for treatment in TREATMENTS:
        print(
            f"  {treatment}: recall {result['recall'][treatment]}, {result['failures'][treatment]} failures, "
            f"{result['material_failures'][treatment]} of them material, "
            f"{result['superseded_serving_cells'][treatment]} cells served superseded"
        )
    print(
        "H13C_VERIFY|"
        + "|".join(
            [
                str(result["requests"]),
                *[result["recall"][treatment] for treatment in TREATMENTS],
                *[result["failures"][treatment] for treatment in TREATMENTS],
                *[str(result["material_failures"][treatment]) for treatment in TREATMENTS],
                str(result["superseded_serving_cells"]["B2"]),
                result["lineage_completeness"],
                str(result["cases"]),
                result["status"],
            ]
        )
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
