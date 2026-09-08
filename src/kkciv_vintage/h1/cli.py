from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .compare import compare_files
from .inventory import indicator_paths, load_indicators, validate_inventory


DEFAULT_SOURCE_REGISTRY = Path("config/sources/bps_sources.csv")
DEFAULT_INDICATOR_DIR = Path("config/indicators")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KK-CIV H1 inventory and comparison harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "summary"):
        command = subparsers.add_parser(name)
        command.add_argument("--source-registry", type=Path, default=DEFAULT_SOURCE_REGISTRY)
        command.add_argument("--indicator-dir", type=Path, default=DEFAULT_INDICATOR_DIR)

    compare = subparsers.add_parser("compare")
    compare.add_argument("--input", type=Path, nargs="+", required=True)
    compare.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "validate":
        errors = validate_inventory(args.source_registry, args.indicator_dir)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        rows = load_indicators(indicator_paths(args.indicator_dir))
        print(f"Inventory valid: {len(rows)} candidate indicators across {len(set(row['domain'] for row in rows))} domains")
        return 0

    if args.command == "summary":
        errors = validate_inventory(args.source_registry, args.indicator_dir)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        rows = load_indicators(indicator_paths(args.indicator_dir))
        counts = Counter((row["domain"], row["verification_status"]) for row in rows)
        for (domain, status), count in sorted(counts.items()):
            print(f"{domain:12} {status:14} {count:2}")
        return 0

    output_rows = compare_files(args.input, args.output)
    counts = Counter(row["status"] for row in output_rows)
    print(f"Wrote {len(output_rows)} compared cells to {args.output}")
    for status, count in sorted(counts.items()):
        print(f"{status:16} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
