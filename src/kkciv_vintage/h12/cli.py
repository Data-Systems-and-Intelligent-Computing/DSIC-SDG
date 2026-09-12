from __future__ import annotations

import argparse
from pathlib import Path

from kkciv_vintage.h11.pipeline import TREATMENTS

from .pipeline import run_aggregate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H12 real-revision application cost"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    aggregate = subparsers.add_parser(
        "aggregate", help="Validate and aggregate the committed raw measurement of the real releases"
    )
    aggregate.add_argument("--contract", type=Path, default=Path("contracts/h12-real-revision-cost.json"))
    aggregate.add_argument("--freeze", type=Path, default=Path("config/experiments/experiment_freeze.csv"))
    aggregate.add_argument(
        "--payload-manifest", type=Path, default=Path("data/manifests/h11-main-sweep-payload.json")
    )
    aggregate.add_argument("--raw-dir", type=Path, default=Path("results/raw/h12/h12-20260913"))
    aggregate.add_argument("--timing-output", type=Path, default=Path("results/processed/h12-statement-timing.csv"))
    aggregate.add_argument("--state-output", type=Path, default=Path("results/processed/h12-arrival-state.csv"))
    aggregate.add_argument("--cost-output", type=Path, default=Path("results/processed/h12-arrival-cost.csv"))
    aggregate.add_argument("--footprint-output", type=Path, default=Path("results/processed/h12-final-footprint.csv"))
    aggregate.add_argument("--validation-output", type=Path, default=Path("results/processed/h12-validation.csv"))
    aggregate.add_argument("--summary-output", type=Path, default=Path("results/processed/h12-summary.csv"))
    aggregate.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h12-real-revision-cost.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "aggregate":
        result = run_aggregate(
            contract_path=args.contract,
            freeze_path=args.freeze,
            payload_manifest_path=args.payload_manifest,
            raw_dir=args.raw_dir,
            timing_output=args.timing_output,
            state_output=args.state_output,
            cost_output=args.cost_output,
            footprint_output=args.footprint_output,
            validation_output=args.validation_output,
            summary_output=args.summary_output,
            manifest_output=args.manifest_output,
        )
        print(
            f"H12 aggregated {result['statements']} statements over {result['repetitions']} repetitions "
            f"of {result['arrivals']} real releases carrying {result['value_changed_rows']} value revisions"
        )
        for treatment in TREATMENTS:
            print(
                f"  {treatment}: {result['totals'][treatment]}s for all four releases; "
                f"{result['final_bytes'][treatment]} referenced bytes afterwards"
            )
        print(
            "H12_VERIFY|"
            + "|".join(
                [
                    str(result["repetitions"]),
                    str(result["arrivals"]),
                    str(result["value_changed_rows"]),
                    *[result["totals"][treatment] for treatment in TREATMENTS],
                    *[result["final_bytes"][treatment] for treatment in TREATMENTS],
                    result["status"],
                ]
            )
        )
        print(f"Manifest: {args.manifest_output}")
        return 0
    raise SystemExit(f"unknown H12 command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
