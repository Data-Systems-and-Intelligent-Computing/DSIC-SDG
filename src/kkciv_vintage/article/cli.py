from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV article data bundle")
    parser.add_argument("--tables", type=Path, default=Path("config/article/bundle_tables.csv"))
    parser.add_argument("--manifest-dir", type=Path, default=Path("data/manifests"))
    parser.add_argument("--output-dir", type=Path, default=Path("papers/vintage_reconciliation/data"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_bundle(tables_config=args.tables, manifest_dir=args.manifest_dir, output_dir=args.output_dir)
    print(
        f"Article bundle: {result['copied_tables']} copied tables, {result['derived_tables']} derived tables, "
        f"{result['key_numbers']} key numbers from {result['verified_sources']} checksum-verified sources"
    )
    print(f"ARTICLE_BUNDLE|{result['copied_tables']}|{result['derived_tables']}|{result['key_numbers']}|{result['verified_sources']}|{result['status']}")
    print(f"Output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
