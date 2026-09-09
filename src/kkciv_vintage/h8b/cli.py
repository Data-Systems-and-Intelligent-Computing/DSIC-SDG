from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h8b


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H8 Jalur B injected-revision harness")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h8b-injected-revision-harness.json"))
    parser.add_argument("--scenarios", type=Path, default=Path("config/h8b/injection_scenarios.csv"))
    parser.add_argument("--human-decisions", type=Path, default=Path("config/h8b/human_decisions.csv"))
    parser.add_argument("--b0-manifest", type=Path, default=Path("data/manifests/h7-b0-overwrite.json"))
    parser.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    parser.add_argument("--plan-output", type=Path, default=Path("results/processed/h8b-injection-plan.csv"))
    parser.add_argument("--injections-output", type=Path, default=Path("results/processed/h8b-injected-revisions.csv"))
    parser.add_argument("--routes-output", type=Path, default=Path("results/processed/h8b-treatment-routes.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h8b-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h8b-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h8b-injected-revision-harness.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h8b(
        contract_path=args.contract,
        scenario_path=args.scenarios,
        human_decisions_path=args.human_decisions,
        b0_manifest_path=args.b0_manifest,
        h6_manifest_path=args.h6_manifest,
        plan_output=args.plan_output,
        injections_output=args.injections_output,
        routes_output=args.routes_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H8B prepared {result['scenario_count']} nested validation scenarios "
        f"({result['scenario_sizes']} cells) over {result['base_cells']} base cells"
    )
    print(
        f"Canonical injected rows={result['injected_rows']}; routes={result['route_rows']} "
        f"for {result['treatment_count']} treatments; status={result['status']}"
    )
    print(
        f"H8B_VERIFY|{result['base_cells']}|{result['scenario_count']}|"
        f"{result['scenario_sizes']}|{result['injected_rows']}|"
        f"{result['treatment_count']}|{result['route_rows']}|"
        f"{result['route_mismatches']}|0|{result['approved_human_decisions']}|"
        f"{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
