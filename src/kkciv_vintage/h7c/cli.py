from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h7c


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H7 Jalur C treatment lineage and literature verification"
    )
    parser.add_argument("--contract", type=Path, default=Path("contracts/h7c-evidence-lineage.json"))
    parser.add_argument("--literature-inventory", type=Path, default=Path("config/h7c/related_work_verification.csv"))
    parser.add_argument("--component-decisions", type=Path, default=Path("config/h7c/component_decisions.csv"))
    parser.add_argument("--related-work", type=Path, default=Path("docs/research/related-work.md"))
    parser.add_argument("--compose", type=Path, default=Path("docker-compose.yml"))
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--h6c-manifest", type=Path, default=Path("data/manifests/h6c-cell-lineage.json"))
    parser.add_argument("--h7-manifest", type=Path, default=Path("data/manifests/h7-b0-overwrite.json"))
    parser.add_argument("--h7b-manifest", type=Path, default=Path("data/manifests/h7b-b2-single-source.json"))
    parser.add_argument("--nodes-output", type=Path, default=Path("results/processed/h7c-lineage-nodes.csv"))
    parser.add_argument("--edges-output", type=Path, default=Path("results/processed/h7c-lineage-edges.csv"))
    parser.add_argument("--treatment-lineage-output", type=Path, default=Path("results/processed/h7c-treatment-lineage.csv"))
    parser.add_argument("--literature-output", type=Path, default=Path("results/processed/h7c-related-work-verification.csv"))
    parser.add_argument("--components-output", type=Path, default=Path("results/processed/h7c-component-status.csv"))
    parser.add_argument("--validation-output", type=Path, default=Path("results/processed/h7c-validation.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h7c-evidence-lineage.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h7c(
        contract_path=args.contract,
        literature_inventory_path=args.literature_inventory,
        component_decisions_path=args.component_decisions,
        related_work_path=args.related_work,
        compose_path=args.compose,
        pyproject_path=args.pyproject,
        h6c_manifest_path=args.h6c_manifest,
        h7_manifest_path=args.h7_manifest,
        h7b_manifest_path=args.h7b_manifest,
        nodes_output=args.nodes_output,
        edges_output=args.edges_output,
        treatment_lineage_output=args.treatment_lineage_output,
        literature_output=args.literature_output,
        components_output=args.components_output,
        validation_output=args.validation_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H7C verified {result['unique_sources']} sources from "
        f"{result['prior_occurrences']} prior daftar occurrences; remaining={result['remaining_daftar']}"
    )
    print(
        f"Lineage={result['combined_nodes']} nodes/{result['combined_edges']} edges; "
        f"treatment paths={result['treatment_paths']}; completeness={result['completeness_rate']}"
    )
    print(
        f"H7C_VERIFY|{result['unique_sources']}|{result['prior_occurrences']}|"
        f"{result['remaining_daftar']}|{result['combined_nodes']}|"
        f"{result['combined_edges']}|{result['treatment_paths']}|"
        f"{result['addressable_requests']}|{result['non_addressable_requests']}|"
        f"{result['completeness_rate']}|{result['optional_components_not_used']}|"
        f"{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
