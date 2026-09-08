from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h2_pilot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H2 free-source comparison")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--indicator-selection", type=Path, default=Path("config/h2/pilot_indicators.csv"))
    run.add_argument("--series-selection", type=Path, default=Path("config/h2/pilot_series.csv"))
    run.add_argument(
        "--publication-reference",
        type=Path,
        default=Path("data/reference/h2/tpb-2024-figure-observations.csv"),
    )
    run.add_argument(
        "--h1-webapi-manifest",
        type=Path,
        default=Path("data/manifests/h1-free-webapi-data.json"),
    )
    run.add_argument(
        "--h1-publication-manifest",
        type=Path,
        default=Path("data/manifests/h1-free-publications.json"),
    )
    run.add_argument(
        "--webapi-output",
        type=Path,
        default=Path("results/processed/h2-webapi-observations.csv"),
    )
    run.add_argument(
        "--publication-output",
        type=Path,
        default=Path("results/processed/h2-publication-observations.csv"),
    )
    run.add_argument(
        "--normalized-output",
        type=Path,
        default=Path("results/processed/h2-normalized-observations.csv"),
    )
    run.add_argument(
        "--comparison-output",
        type=Path,
        default=Path("results/processed/h2-cell-comparison.csv"),
    )
    run.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/processed/h2-indicator-summary.csv"),
    )
    run.add_argument(
        "--discrepancy-output",
        type=Path,
        default=Path("results/processed/h2-discrepancies.csv"),
    )
    run.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h2-normalization.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h2_pilot(
        indicator_selection=args.indicator_selection,
        series_selection=args.series_selection,
        publication_reference=args.publication_reference,
        h1_webapi_manifest=args.h1_webapi_manifest,
        h1_publication_manifest=args.h1_publication_manifest,
        webapi_output=args.webapi_output,
        publication_output=args.publication_output,
        normalized_output=args.normalized_output,
        comparison_output=args.comparison_output,
        discrepancy_output=args.discrepancy_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H2 wrote {result['webapi_rows']} WebAPI observations, "
        f"{result['publication_rows']} publication observations, and "
        f"{result['comparison_rows']} compared cells; "
        f"{result['discrepancy_rows']} cells require follow-up"
    )
    for status, count in sorted(result["statuses"].items()):
        print(f"  {status:18} {count:2}")
    print(f"Summary: {args.summary_output}")
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
