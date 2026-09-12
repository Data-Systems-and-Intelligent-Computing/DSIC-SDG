from __future__ import annotations

import argparse
from pathlib import Path

from kkciv_vintage.h11.pipeline import TREATMENTS

from .pipeline import run_h14


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H14 query plans, session logs and read statistics"
    )
    parser.add_argument("--contract", type=Path, default=Path("contracts/h14-plan-and-read-statistics.json"))
    parser.add_argument("--raw-dir", type=Path, default=Path("results/raw/h14/h14-20260913"))
    parser.add_argument("--read-output", type=Path, default=Path("results/processed/h14-read-statistics.csv"))
    parser.add_argument(
        "--read-summary-output", type=Path, default=Path("results/processed/h14-read-summary.csv")
    )
    parser.add_argument("--plan-output", type=Path, default=Path("results/processed/h14-query-plans.csv"))
    parser.add_argument(
        "--artifact-output", type=Path, default=Path("results/processed/h14-artifact-inventory.csv")
    )
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h14-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h14-summary.csv"))
    parser.add_argument(
        "--manifest-output", type=Path, default=Path("data/manifests/h14-plan-and-read-statistics.json")
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h14(
        contract_path=args.contract,
        raw_dir=args.raw_dir,
        read_output=args.read_output,
        read_summary_output=args.read_summary_output,
        plan_output=args.plan_output,
        artifact_output=args.artifact_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H14 collected {result['executions']} instrumented scans over {result['repetitions']} repetitions "
        f"and {result['scenarios']} sweep points, plus {result['plans']} plans and {result['artifacts']} "
        f"preserved artifacts ({result['artifact_bytes']} bytes)"
    )
    for treatment in TREATMENTS:
        print(
            f"  {treatment}: reads {result['bytes_read'][treatment]} bytes from "
            f"{result['files_read'][treatment]} data files at the largest sweep point"
        )
    print(
        "H14_VERIFY|"
        + "|".join(
            [
                str(result["repetitions"]),
                str(result["scenarios"]),
                str(result["executions"]),
                *[result["bytes_read"][treatment] for treatment in TREATMENTS],
                str(result["plans"]),
                str(result["artifacts"]),
                result["status"],
            ]
        )
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
