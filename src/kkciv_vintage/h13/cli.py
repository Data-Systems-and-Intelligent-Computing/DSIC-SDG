from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h13


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H13 rerun of the doubtful measurement points"
    )
    parser.add_argument("--contract", type=Path, default=Path("contracts/h13-rerun-stability.json"))
    parser.add_argument("--h11-timing", type=Path, default=Path("results/processed/h11-statement-timing.csv"))
    parser.add_argument("--h12-timing", type=Path, default=Path("results/processed/h12-statement-timing.csv"))
    parser.add_argument(
        "--h11-payload-manifest", type=Path, default=Path("data/manifests/h11-main-sweep-payload.json")
    )
    parser.add_argument("--h11-rerun-dir", type=Path, default=Path("results/raw/h11/h13-h11-sweep001"))
    parser.add_argument("--h12-rerun-dir", type=Path, default=Path("results/raw/h12/h13-h12"))
    parser.add_argument("--doubt-output", type=Path, default=Path("results/processed/h13-doubtful-points.csv"))
    parser.add_argument("--stability-output", type=Path, default=Path("results/processed/h13-stability.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h13-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h13-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h13-rerun-stability.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h13(
        contract_path=args.contract,
        h11_timing_path=args.h11_timing,
        h12_timing_path=args.h12_timing,
        h11_payload_manifest=args.h11_payload_manifest,
        h11_rerun_dir=args.h11_rerun_dir,
        h12_rerun_dir=args.h12_rerun_dir,
        doubt_output=args.doubt_output,
        stability_output=args.stability_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H13 checked {result['points_checked']} measurement points, found {result['points_doubtful']} "
        f"doubtful, and added {result['repetitions_added']} repetitions to {result['points_rerun']} of them"
    )
    print(
        f"  {result['points_stable']} stable, {result['points_shifted']} shifted; "
        f"largest shift {result['largest_shift']}"
    )
    print(
        "H13_VERIFY|"
        + "|".join(
            [
                str(result["points_checked"]),
                str(result["points_doubtful"]),
                str(result["points_rerun"]),
                str(result["repetitions_added"]),
                str(result["points_stable"]),
                str(result["points_shifted"]),
                result["largest_shift"],
                result["status"],
            ]
        )
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
