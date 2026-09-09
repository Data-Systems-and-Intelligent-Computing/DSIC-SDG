from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h6c


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H6 Jalur C cell-level lineage")
    parser.add_argument(
        "--contract", type=Path, default=Path("contracts/h6c-cell-lineage.json")
    )
    parser.add_argument(
        "--h6-manifest", type=Path, default=Path("data/manifests/h6-vintage-schema.json")
    )
    parser.add_argument(
        "--nodes-output",
        type=Path,
        default=Path("results/processed/h6c-lineage-nodes.csv"),
    )
    parser.add_argument(
        "--edges-output",
        type=Path,
        default=Path("results/processed/h6c-lineage-edges.csv"),
    )
    parser.add_argument(
        "--paths-output",
        type=Path,
        default=Path("results/processed/h6c-cell-source-paths.csv"),
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        default=Path("results/processed/h6c-lineage-validation.csv"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h6c-cell-lineage.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h6c(
        contract_path=args.contract,
        h6_manifest_path=args.h6_manifest,
        nodes_output=args.nodes_output,
        edges_output=args.edges_output,
        paths_output=args.paths_output,
        validation_output=args.validation_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H6C mapped {result['path_count']} observation paths across "
        f"{result['cell_count']} cells; completeness={result['completeness_rate']}"
    )
    print(
        f"Graph={result['node_count']} nodes/{result['edge_count']} edges; "
        f"raw locator collisions={result['raw_locator_collision_groups']} groups/"
        f"{result['raw_locator_collision_observations']} observations"
    )
    print(
        f"H6C_VERIFY|{result['node_count']}|{result['edge_count']}|"
        f"{result['path_count']}|{result['cell_count']}|"
        f"{result['raw_locator_collision_groups']}|"
        f"{result['raw_locator_collision_observations']}|"
        f"{result['completeness_rate']}|{result['status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
