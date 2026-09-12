from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_aggregate, run_prepare


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H10 track B physical injected-revision execution"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare", help="Build the physical payload and the expected outcome of every scenario"
    )
    prepare.add_argument("--contract", type=Path, default=Path("contracts/h10b-injected-revision-physical.json"))
    prepare.add_argument("--decisions", type=Path, default=Path("config/h10/human_decisions.csv"))
    prepare.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    prepare.add_argument("--h6b-manifest", type=Path, default=Path("data/manifests/h6b-source-trust.json"))
    prepare.add_argument("--h6c-manifest", type=Path, default=Path("data/manifests/h6c-cell-lineage.json"))
    prepare.add_argument("--h8b-manifest", type=Path, default=Path("data/manifests/h8b-injected-revision-harness.json"))
    prepare.add_argument("--h9b-contract", type=Path, default=Path("contracts/h9b-small-revision-execution.json"))
    prepare.add_argument("--h9b-manifest", type=Path, default=Path("data/manifests/h9b-small-revision-execution.json"))
    prepare.add_argument("--b2-contract", type=Path, default=Path("contracts/h7b-b2-single-source.json"))
    prepare.add_argument("--scenarios-output", type=Path, default=Path("results/processed/h10b-physical-scenarios.csv"))
    prepare.add_argument("--store-output", type=Path, default=Path("results/processed/h10b-synthetic-observations.csv"))
    prepare.add_argument("--b1-output", type=Path, default=Path("results/processed/h10b-b1-next-state.csv"))
    prepare.add_argument("--b2-output", type=Path, default=Path("results/processed/h10b-b2-next-state.csv"))
    prepare.add_argument("--dirty-output", type=Path, default=Path("results/processed/h10b-b3-dirty-cells.csv"))
    prepare.add_argument("--expected-state-output", type=Path, default=Path("results/processed/h10b-expected-state.csv"))
    prepare.add_argument("--expected-recall-output", type=Path, default=Path("results/processed/h10b-expected-recall.csv"))
    prepare.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h10b-physical-payload.json"))

    aggregate = subparsers.add_parser(
        "aggregate", help="Validate and aggregate the committed raw measurement of a physical run"
    )
    aggregate.add_argument("--contract", type=Path, default=Path("contracts/h10b-injected-revision-physical.json"))
    aggregate.add_argument("--decisions", type=Path, default=Path("config/h10/human_decisions.csv"))
    aggregate.add_argument("--raw-dir", type=Path, default=Path("results/raw/h10b/h10b-20260912"))
    aggregate.add_argument("--cleanup-dir", type=Path, default=Path("results/raw/h10b/cleanup-20260912"))
    aggregate.add_argument("--payload-manifest", type=Path, default=Path("data/manifests/h10b-physical-payload.json"))
    aggregate.add_argument("--timing-output", type=Path, default=Path("results/processed/h10b-statement-timing.csv"))
    aggregate.add_argument("--apply-cost-output", type=Path, default=Path("results/processed/h10b-apply-cost.csv"))
    aggregate.add_argument("--storage-output", type=Path, default=Path("results/processed/h10b-storage-delta.csv"))
    aggregate.add_argument("--recall-output", type=Path, default=Path("results/processed/h10b-recall-after-revision.csv"))
    aggregate.add_argument("--orphan-output", type=Path, default=Path("results/processed/h10b-orphan-cleanup.csv"))
    aggregate.add_argument("--validation-output", type=Path, default=Path("results/processed/h10b-validation.csv"))
    aggregate.add_argument("--summary-output", type=Path, default=Path("results/processed/h10b-summary.csv"))
    aggregate.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h10b-injected-revision-physical.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "prepare":
        result = run_prepare(
            contract_path=args.contract,
            decisions_path=args.decisions,
            h6_manifest_path=args.h6_manifest,
            h6b_manifest_path=args.h6b_manifest,
            h6c_manifest_path=args.h6c_manifest,
            h8b_manifest_path=args.h8b_manifest,
            h9b_contract_path=args.h9b_contract,
            h9b_manifest_path=args.h9b_manifest,
            b2_contract_path=args.b2_contract,
            scenarios_output=args.scenarios_output,
            store_output=args.store_output,
            b1_output=args.b1_output,
            b2_output=args.b2_output,
            dirty_output=args.dirty_output,
            expected_state_output=args.expected_state_output,
            expected_recall_output=args.expected_recall_output,
            manifest_output=args.manifest_output,
        )
        print(
            f"H10B prepared {result['scenarios']} physical scenarios with {result['synthetic_rows']} synthetic rows, "
            f"{result['expected_states']} expected state rows, and {result['expected_requests']} expected requests"
        )
        print(f"Manifest: {args.manifest_output}")
        return 0
    if args.command == "aggregate":
        result = run_aggregate(
            contract_path=args.contract,
            decisions_path=args.decisions,
            raw_dir=args.raw_dir,
            cleanup_dir=args.cleanup_dir,
            payload_manifest_path=args.payload_manifest,
            timing_output=args.timing_output,
            apply_cost_output=args.apply_cost_output,
            storage_output=args.storage_output,
            recall_output=args.recall_output,
            orphan_output=args.orphan_output,
            validation_output=args.validation_output,
            summary_output=args.summary_output,
            manifest_output=args.manifest_output,
        )
        seconds = result["write_seconds"]
        delta = result["delta_bytes"]
        print(
            f"H10B executed {result['routes']} physical routes over {result['repetitions']} repetitions; "
            f"{result['first_scenario']} write seconds B0={seconds['B0']} B1={seconds['B1']} "
            f"B2={seconds['B2']} B3={seconds['B3']}"
        )
        print(
            f"H10B_VERIFY|{result['repetitions']}|{result['scenarios']}|{result['routes']}|"
            f"{result['orphan_objects']}|{result['orphan_bytes']}|"
            f"{seconds['B0']}|{seconds['B1']}|{seconds['B2']}|{seconds['B3']}|"
            f"{delta['B0']}|{delta['B1']}|{delta['B2']}|{delta['B3']}|"
            f"{result['recalled']['B0']}|{result['recalled']['B1']}|{result['recalled']['B2']}|"
            f"{result['recalled']['B3']}|{result['status']}"
        )
        print(f"Manifest: {args.manifest_output}")
        return 0
    raise SystemExit(f"unknown H10B command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
