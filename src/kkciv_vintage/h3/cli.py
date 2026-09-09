from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h3, run_h3_release_supplement


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H3 national and province comparison")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--indicators", type=Path, default=Path("config/h3/province_indicators.csv"))
    run.add_argument("--columns", type=Path, default=Path("config/h3/province_columns.csv"))
    run.add_argument("--webapi-manifest", type=Path, default=Path("data/manifests/h1-free-webapi-data.json"))
    run.add_argument("--publication-manifest", type=Path, default=Path("data/manifests/h1-free-publications.json"))
    run.add_argument("--webapi-output", type=Path, default=Path("results/processed/h3-webapi-observations.csv"))
    run.add_argument("--publication-output", type=Path, default=Path("results/processed/h3-publication-observations.csv"))
    run.add_argument("--comparison-output", type=Path, default=Path("results/processed/h3-cell-comparison.csv"))
    run.add_argument("--discrepancy-output", type=Path, default=Path("results/processed/h3-discrepancies.csv"))
    run.add_argument("--granularity-output", type=Path, default=Path("results/processed/h3-granularity.csv"))
    run.add_argument("--summary-output", type=Path, default=Path("results/processed/h3-indicator-summary.csv"))
    run.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h3-comparison.json"))

    releases = subparsers.add_parser("releases")
    releases.add_argument("--webapi-manifest", type=Path, default=Path("data/manifests/h3-free-webapi-data.json"))
    releases.add_argument("--webapi-series", type=Path, default=Path("config/h3/webapi_series.csv"))
    releases.add_argument("--publication-series", type=Path, default=Path("config/h3/publication_series.csv"))
    releases.add_argument("--publication-manifest", type=Path, default=Path("data/manifests/h1-free-publications.json"))
    releases.add_argument("--exclusions", type=Path, default=Path("config/h3/exclusions.csv"))
    releases.add_argument("--webapi-output", type=Path, default=Path("results/processed/h3-release-webapi-observations.csv"))
    releases.add_argument("--publication-output", type=Path, default=Path("results/processed/h3-release-publication-observations.csv"))
    releases.add_argument("--normalized-output", type=Path, default=Path("results/processed/h3-release-normalized-observations.csv"))
    releases.add_argument("--comparison-output", type=Path, default=Path("results/processed/h3-release-cell-comparison.csv"))
    releases.add_argument("--discrepancy-output", type=Path, default=Path("results/processed/h3-release-discrepancies.csv"))
    releases.add_argument("--summary-output", type=Path, default=Path("results/processed/h3-release-domain-summary.csv"))
    releases.add_argument("--chart-scope-output", type=Path, default=Path("results/processed/h3-release-chart-scope.csv"))
    releases.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h3-release-reconciliation.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "run":
        result = run_h3(
            indicators_path=args.indicators,
            columns_path=args.columns,
            webapi_manifest_path=args.webapi_manifest,
            publication_manifest_path=args.publication_manifest,
            webapi_output=args.webapi_output,
            publication_output=args.publication_output,
            comparison_output=args.comparison_output,
            discrepancy_output=args.discrepancy_output,
            granularity_output=args.granularity_output,
            summary_output=args.summary_output,
            manifest_output=args.manifest_output,
        )
        print(
            f"H3 compared {result['comparison_rows']} national/province cells; "
            f"{result['discrepancy_rows']} differ and "
            f"{result['granularity_rows']} national/province checks were written"
        )
        print(f"Manifest: {args.manifest_output}")
        return 0

    result = run_h3_release_supplement(
        webapi_manifest=args.webapi_manifest,
        webapi_series=args.webapi_series,
        publication_series=args.publication_series,
        publication_manifest=args.publication_manifest,
        exclusions=args.exclusions,
        webapi_output=args.webapi_output,
        publication_output=args.publication_output,
        normalized_output=args.normalized_output,
        comparison_output=args.comparison_output,
        discrepancy_output=args.discrepancy_output,
        summary_output=args.summary_output,
        chart_scope_output=args.chart_scope_output,
        manifest_output=args.manifest_output,
    )
    domains = ", ".join(result["mismatch_domains"]) or "none"
    print(
        f"H3 release supplement compared {result['comparison_rows']} cells; "
        f"{result['discrepancy_rows']} differ in domains: {domains}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
