from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import TREATMENTS, run_aggregate, run_prepare


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H11 main injected-revision sweep")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare",
        help="Project the frozen panel, rebuild the frozen sweep payload, and predict every outcome",
    )
    prepare.add_argument("--contract", type=Path, default=Path("contracts/h11-main-sweep.json"))
    prepare.add_argument("--decisions", type=Path, default=Path("config/h10c/human_decisions.csv"))
    prepare.add_argument("--freeze", type=Path, default=Path("config/experiments/experiment_freeze.csv"))
    prepare.add_argument("--scenarios", type=Path, default=Path("config/experiments/main_sweep_scenarios.csv"))
    prepare.add_argument("--universe", type=Path, default=Path("config/experiments/main_sweep_universe.csv"))
    prepare.add_argument("--panel", type=Path, default=Path("results/processed/h4-ingested-observations.csv"))
    prepare.add_argument("--scores", type=Path, default=Path("results/processed/h6b-source-trust-scores.csv"))
    prepare.add_argument("--b2-contract", type=Path, default=Path("contracts/h7b-b2-single-source.json"))
    prepare.add_argument("--panel-vintages-output", type=Path, default=Path("results/processed/h11-panel-vintages.csv"))
    prepare.add_argument(
        "--panel-observations-output", type=Path, default=Path("results/processed/h11-panel-observations.csv")
    )
    prepare.add_argument("--duplicates-output", type=Path, default=Path("results/processed/h11-panel-duplicates.csv"))
    prepare.add_argument(
        "--impact-edges-output", type=Path, default=Path("results/processed/h11-panel-impact-edges.csv")
    )
    prepare.add_argument("--b1-catalog-output", type=Path, default=Path("results/processed/h11-b1-state-catalog.csv"))
    prepare.add_argument("--baseline-output", type=Path, default=Path("results/processed/h11-baseline-expectations.csv"))
    prepare.add_argument("--plans-output", type=Path, default=Path("results/processed/h11-sweep-plans.csv"))
    prepare.add_argument("--injections-output", type=Path, default=Path("results/processed/h11-sweep-injections.csv"))
    prepare.add_argument(
        "--synthetic-output", type=Path, default=Path("results/processed/h11-sweep-synthetic-observations.csv")
    )
    prepare.add_argument(
        "--synthetic-vintages-output", type=Path, default=Path("results/processed/h11-sweep-vintages.csv")
    )
    prepare.add_argument("--dirty-output", type=Path, default=Path("results/processed/h11-b3-dirty-cells.csv"))
    prepare.add_argument("--scenarios-output", type=Path, default=Path("results/processed/h11-sweep-scenarios.csv"))
    prepare.add_argument(
        "--expected-revised-output", type=Path, default=Path("results/processed/h11-expected-revised.csv")
    )
    prepare.add_argument(
        "--expected-recall-output", type=Path, default=Path("results/processed/h11-expected-recall.csv")
    )
    prepare.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h11-main-sweep-payload.json"))
    aggregate = subparsers.add_parser(
        "aggregate", help="Validate and aggregate the committed raw measurement of the main sweep"
    )
    aggregate.add_argument("--contract", type=Path, default=Path("contracts/h11-main-sweep.json"))
    aggregate.add_argument("--decisions", type=Path, default=Path("config/h10c/human_decisions.csv"))
    aggregate.add_argument("--freeze", type=Path, default=Path("config/experiments/experiment_freeze.csv"))
    aggregate.add_argument(
        "--payload-manifest", type=Path, default=Path("data/manifests/h11-main-sweep-payload.json")
    )
    aggregate.add_argument("--raw-dir", type=Path, default=Path("results/raw/h11/h11-20260913"))
    aggregate.add_argument("--timing-output", type=Path, default=Path("results/processed/h11-statement-timing.csv"))
    aggregate.add_argument("--apply-cost-output", type=Path, default=Path("results/processed/h11-apply-cost.csv"))
    aggregate.add_argument("--storage-output", type=Path, default=Path("results/processed/h11-storage-delta.csv"))
    aggregate.add_argument("--recall-output", type=Path, default=Path("results/processed/h11-recall.csv"))
    aggregate.add_argument("--propagation-output", type=Path, default=Path("results/processed/h11-propagation.csv"))
    aggregate.add_argument("--injection-output", type=Path, default=Path("results/processed/h11-injection-audit.csv"))
    aggregate.add_argument("--breakeven-output", type=Path, default=Path("results/processed/h11-breakeven.csv"))
    aggregate.add_argument("--validation-output", type=Path, default=Path("results/processed/h11-validation.csv"))
    aggregate.add_argument("--summary-output", type=Path, default=Path("results/processed/h11-summary.csv"))
    aggregate.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h11-main-sweep.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "prepare":
        result = run_prepare(
            contract_path=args.contract,
            decisions_path=args.decisions,
            freeze_path=args.freeze,
            scenarios_path=args.scenarios,
            universe_path=args.universe,
            panel_path=args.panel,
            scores_path=args.scores,
            b2_contract_path=args.b2_contract,
            panel_vintages_output=args.panel_vintages_output,
            panel_observations_output=args.panel_observations_output,
            duplicates_output=args.duplicates_output,
            impact_edges_output=args.impact_edges_output,
            b1_catalog_output=args.b1_catalog_output,
            baseline_output=args.baseline_output,
            plans_output=args.plans_output,
            injections_output=args.injections_output,
            synthetic_output=args.synthetic_output,
            synthetic_vintages_output=args.synthetic_vintages_output,
            dirty_output=args.dirty_output,
            scenarios_output=args.scenarios_output,
            expected_revised_output=args.expected_revised_output,
            expected_recall_output=args.expected_recall_output,
            manifest_output=args.manifest_output,
        )
        print(
            f"H11 prepared {result['scenarios']} sweep points over a panel of "
            f"{result['observations']} observations on {result['cells']} cells "
            f"({result['vintages']} vintages, {result['duplicates']} duplicates dropped)"
        )
        for table, rows in result["baseline_rows"].items():
            print(f"  baseline {table}: {rows} rows")
        print(f"Manifest: {args.manifest_output}")
        return 0
    if args.command == "aggregate":
        result = run_aggregate(
            contract_path=args.contract,
            decisions_path=args.decisions,
            freeze_path=args.freeze,
            payload_manifest_path=args.payload_manifest,
            raw_dir=args.raw_dir,
            timing_output=args.timing_output,
            apply_cost_output=args.apply_cost_output,
            storage_output=args.storage_output,
            recall_output=args.recall_output,
            propagation_output=args.propagation_output,
            injection_output=args.injection_output,
            breakeven_output=args.breakeven_output,
            validation_output=args.validation_output,
            summary_output=args.summary_output,
            manifest_output=args.manifest_output,
        )
        seconds = result["seconds"]
        deltas = result["delta_bytes"]
        print(
            f"H11 aggregated {result['routes']} routes over {result['repetitions']} repetitions "
            f"and {result['scenarios']} sweep points on {result['panel_cells']} panel cells"
        )
        for treatment in TREATMENTS:
            print(
                f"  {treatment}: {seconds[treatment]['smallest']}s at the smallest point, "
                f"{seconds[treatment]['largest']}s at one full year; "
                f"{deltas[treatment]['smallest']} to {deltas[treatment]['largest']} bytes added; "
                f"recall {result['recall'][treatment]}"
            )
        for key, crossing in result["breakeven"].items():
            print(f"  break-even {key}: {crossing}")
        print(
            "H11_VERIFY|"
            + "|".join(
                [
                    str(result["repetitions"]),
                    str(result["scenarios"]),
                    str(result["routes"]),
                    str(result["panel_observations"]),
                    str(result["panel_cells"]),
                    *[seconds[treatment]["smallest"] for treatment in TREATMENTS],
                    *[seconds[treatment]["largest"] for treatment in TREATMENTS],
                    *[deltas[treatment]["largest"] for treatment in TREATMENTS],
                    *[result["recall"][treatment] for treatment in TREATMENTS],
                    result["breakeven"]["B3|B1|total_seconds_median"],
                    result["breakeven"]["B3|B1|delta_bytes_median"],
                    result["status"],
                ]
            )
        )
        print(f"Manifest: {args.manifest_output}")
        return 0
    raise SystemExit(f"unknown H11 command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
