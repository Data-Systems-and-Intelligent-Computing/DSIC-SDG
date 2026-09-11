from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h9c


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H9 Jalur C B3 lineage and audit")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h9c-b3-lineage-audit.json"))
    parser.add_argument("--procedure", type=Path, default=Path("config/h8c/reproducibility_audit_steps.csv"))
    parser.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    parser.add_argument("--h6c-manifest", type=Path, default=Path("data/manifests/h6c-cell-lineage.json"))
    parser.add_argument("--h8c-manifest", type=Path, default=Path("data/manifests/h8c-reproducibility-lineage.json"))
    parser.add_argument("--h9-manifest", type=Path, default=Path("data/manifests/h9-b3-vintage-aware.json"))
    parser.add_argument("--audit-output", type=Path, default=Path("results/processed/h9c-reproducibility-audit.csv"))
    parser.add_argument("--impact-audit-output", type=Path, default=Path("results/processed/h9c-impact-audit.csv"))
    parser.add_argument("--metrics-output", type=Path, default=Path("results/processed/h9c-reproducibility-metrics.csv"))
    parser.add_argument("--table-output", type=Path, default=Path("results/processed/h9c-reproducibility-table.csv"))
    parser.add_argument("--figure-output", type=Path, default=Path("results/processed/h9c-reproducibility-figure-data.csv"))
    parser.add_argument("--nodes-output", type=Path, default=Path("results/processed/h9c-lineage-nodes.csv"))
    parser.add_argument("--edges-output", type=Path, default=Path("results/processed/h9c-lineage-edges.csv"))
    parser.add_argument("--closure-output", type=Path, default=Path("results/processed/h9c-evidence-closure.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h9c-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h9c-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h9c-b3-lineage-audit.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h9c(
        contract_path=args.contract,
        procedure_path=args.procedure,
        h6_manifest_path=args.h6_manifest,
        h6c_manifest_path=args.h6c_manifest,
        h8c_manifest_path=args.h8c_manifest,
        h9_manifest_path=args.h9_manifest,
        audit_output=args.audit_output,
        impact_audit_output=args.impact_audit_output,
        metrics_output=args.metrics_output,
        table_output=args.table_output,
        figure_output=args.figure_output,
        nodes_output=args.nodes_output,
        edges_output=args.edges_output,
        closure_output=args.closure_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H9C audited {result['audit_requests']} requests across {result['treatments']} treatments; "
        f"addressable={result['addressable']}, unavailable={result['unavailable']}; "
        f"B3={result['b3_addressable']}/{result['b3_requests']}"
    )
    print(
        f"Impact audit={result['impact_rows']} rows, mismatches={result['impact_mismatches']}; "
        f"closure={result['closed_nodes']} nodes/{result['closed_edges']} edges/"
        f"{result['audit_requests']} paths; completeness={result['completeness']}"
    )
    print(
        f"H9C_VERIFY|{result['base_nodes']}|{result['base_edges']}|"
        f"{result['closed_nodes']}|{result['closed_edges']}|{result['audit_requests']}|"
        f"{result['addressable']}|{result['unavailable']}|{result['completeness']}|"
        f"{result['treatments']}|{result['b3_addressable']}|{result['impact_rows']}|"
        f"{result['impact_mismatches']}|{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
