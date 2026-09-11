from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H10 track A storage footprint and recall after restart")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h10-storage-recall.json"))
    parser.add_argument("--decisions", type=Path, default=Path("config/h10/human_decisions.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("results/raw/h10/h10a-20260911"))
    parser.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    parser.add_argument("--b1-manifest", type=Path, default=Path("data/manifests/h8-b1-full-snapshot.json"))
    parser.add_argument("--h9c-manifest", type=Path, default=Path("data/manifests/h9c-b3-lineage-audit.json"))
    parser.add_argument("--files-output", type=Path, default=Path("results/processed/h10-storage-objects.csv"))
    parser.add_argument("--footprint-output", type=Path, default=Path("results/processed/h10-storage-footprint.csv"))
    parser.add_argument("--tables-output", type=Path, default=Path("results/processed/h10-storage-tables.csv"))
    parser.add_argument("--treatment-summary-output", type=Path, default=Path("results/processed/h10-storage-by-treatment.csv"))
    parser.add_argument("--recall-output", type=Path, default=Path("results/processed/h10-recall-after-restart.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h10-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h10-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h10-storage-recall.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h10(
        contract_path=args.contract,
        decisions_path=args.decisions,
        raw_dir=args.raw_dir,
        h6_manifest_path=args.h6_manifest,
        b1_manifest_path=args.b1_manifest,
        h9c_manifest_path=args.h9c_manifest,
        files_output=args.files_output,
        footprint_output=args.footprint_output,
        tables_output=args.tables_output,
        treatment_summary_output=args.treatment_summary_output,
        recall_output=args.recall_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H10A measured {result['objects']} referenced objects over {result['repetitions']} repetitions; "
        f"median bytes B0={result['b0_bytes']} B1={result['b1_bytes']} B2={result['b2_bytes']} B3={result['b3_bytes']}"
    )
    print(
        f"H10_VERIFY|{result['repetitions']}|{result['b0_bytes']}|{result['b1_bytes']}|{result['b2_bytes']}|"
        f"{result['b3_bytes']}|{result['b0_recalled']}|{result['b1_recalled']}|{result['b2_recalled']}|"
        f"{result['b3_recalled']}|{'stable' if result['stable'] else 'variable'}|{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
