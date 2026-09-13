from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h14c


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H14 track C break-even decomposition and failure synthesis"
    )
    parser.add_argument(
        "--contract", type=Path, default=Path("contracts/h14c-breakeven-and-failure-analysis.json")
    )
    parser.add_argument("--sweep-cost", type=Path, default=Path("results/processed/h11-apply-cost.csv"))
    parser.add_argument("--breakeven", type=Path, default=Path("results/processed/h11-breakeven.csv"))
    parser.add_argument("--real-cost", type=Path, default=Path("results/processed/h12-arrival-cost.csv"))
    parser.add_argument("--reads", type=Path, default=Path("results/processed/h14-read-summary.csv"))
    parser.add_argument(
        "--audit", type=Path, default=Path("results/processed/h13c-reproducibility-table.csv")
    )
    parser.add_argument("--profile", type=Path, default=Path("results/processed/h13c-failure-profile.csv"))
    parser.add_argument("--cases", type=Path, default=Path("results/processed/h13c-failure-cases.csv"))
    parser.add_argument("--scenarios", type=Path, default=Path("results/processed/h11-sweep-scenarios.csv"))
    parser.add_argument(
        "--decomposition-output", type=Path, default=Path("results/processed/h14c-cost-decomposition.csv")
    )
    parser.add_argument(
        "--conditions-output", type=Path, default=Path("results/processed/h14c-breakeven-conditions.csv")
    )
    parser.add_argument(
        "--cost-output", type=Path, default=Path("results/processed/h14c-cost-of-reproducibility.csv")
    )
    parser.add_argument(
        "--failure-output", type=Path, default=Path("results/processed/h14c-failure-synthesis.csv")
    )
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h14c-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h14c-summary.csv"))
    parser.add_argument(
        "--manifest-output", type=Path, default=Path("data/manifests/h14c-breakeven-and-failure-analysis.json")
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h14c(
        contract_path=args.contract,
        sweep_cost_path=args.sweep_cost,
        breakeven_path=args.breakeven,
        real_cost_path=args.real_cost,
        reads_path=args.reads,
        audit_path=args.audit,
        profile_path=args.profile,
        cases_path=args.cases,
        scenarios_path=args.scenarios,
        decomposition_output=args.decomposition_output,
        conditions_output=args.conditions_output,
        cost_output=args.cost_output,
        failure_output=args.failure_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H14C decomposed {result['decomposition_rows']} cost lines, checked {result['conditions']} "
        f"break-even conditions and synthesised {result['failure_kinds']} failure kinds"
    )
    print(
        f"  measured crossings inside the sweep: {result['measured_crossings']}; "
        f"projections outside it: {result['projections']}"
    )
    print(
        f"  treatments keeping every published figure: {','.join(result['keeping_treatments'])}; "
        f"material figures at stake: {result['material_figures']}"
    )
    print(
        "H14C_VERIFY|"
        + "|".join(
            [
                str(result["decomposition_rows"]),
                str(result["conditions"]),
                str(result["projections"]),
                str(result["measured_crossings"]),
                str(result["failure_kinds"]),
                str(result["material_figures"]),
                ",".join(result["keeping_treatments"]),
                result["status"],
            ]
        )
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
