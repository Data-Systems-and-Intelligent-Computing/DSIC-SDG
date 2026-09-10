from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h8c


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H8 Jalur C evidence closure")
    parser.add_argument("--contract", type=Path, default=Path("contracts/h8c-reproducibility-lineage.json"))
    parser.add_argument("--procedure", type=Path, default=Path("config/h8c/reproducibility_audit_steps.csv"))
    parser.add_argument("--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json"))
    parser.add_argument("--h6c-manifest", type=Path, default=Path("data/manifests/h6c-cell-lineage.json"))
    parser.add_argument("--h7c-manifest", type=Path, default=Path("data/manifests/h7c-evidence-lineage.json"))
    parser.add_argument("--b0-manifest", type=Path, default=Path("data/manifests/h7-b0-overwrite.json"))
    parser.add_argument("--b1-manifest", type=Path, default=Path("data/manifests/h8-b1-full-snapshot.json"))
    parser.add_argument("--b2-manifest", type=Path, default=Path("data/manifests/h7b-b2-single-source.json"))
    parser.add_argument("--h8b-manifest", type=Path, default=Path("data/manifests/h8b-injected-revision-harness.json"))
    parser.add_argument("--audit-output", type=Path, default=Path("results/processed/h8c-reproducibility-audit.csv"))
    parser.add_argument("--metrics-output", type=Path, default=Path("results/processed/h8c-reproducibility-metrics.csv"))
    parser.add_argument("--table-output", type=Path, default=Path("results/processed/h8c-reproducibility-table.csv"))
    parser.add_argument("--figure-output", type=Path, default=Path("results/processed/h8c-reproducibility-figure-data.csv"))
    parser.add_argument("--nodes-output", type=Path, default=Path("results/processed/h8c-lineage-nodes.csv"))
    parser.add_argument("--edges-output", type=Path, default=Path("results/processed/h8c-lineage-edges.csv"))
    parser.add_argument("--closure-output", type=Path, default=Path("results/processed/h8c-evidence-closure.csv"))
    parser.add_argument("--procedure-output", type=Path, default=Path("results/processed/h8c-audit-procedure.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h8c-validation.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("results/processed/h8c-summary.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h8c-reproducibility-lineage.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h8c(
        contract_path=args.contract,
        procedure_path=args.procedure,
        h6_manifest_path=args.h6_manifest,
        h6c_manifest_path=args.h6c_manifest,
        h7c_manifest_path=args.h7c_manifest,
        b0_manifest_path=args.b0_manifest,
        b1_manifest_path=args.b1_manifest,
        b2_manifest_path=args.b2_manifest,
        h8b_manifest_path=args.h8b_manifest,
        audit_output=args.audit_output,
        metrics_output=args.metrics_output,
        table_output=args.table_output,
        figure_output=args.figure_output,
        nodes_output=args.nodes_output,
        edges_output=args.edges_output,
        closure_output=args.closure_output,
        procedure_output=args.procedure_output,
        validation_output=args.validation_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H8C audited {result['audit_requests']} requests across {result['treatments']} "
        f"implemented treatments; addressable={result['addressable']}, unavailable={result['unavailable']}"
    )
    print(
        f"Evidence closure={result['closed_nodes']} nodes/{result['closed_edges']} edges/"
        f"{result['audit_requests']} paths; completeness={result['completeness']}"
    )
    print(
        f"H8C_VERIFY|{result['base_nodes']}|{result['base_edges']}|"
        f"{result['closed_nodes']}|{result['closed_edges']}|{result['audit_requests']}|"
        f"{result['addressable']}|{result['unavailable']}|{result['completeness']}|"
        f"{result['treatments']}|{result['steps']}|{result['pipeline_steps']}|"
        f"{result['adapter_steps']}|{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
