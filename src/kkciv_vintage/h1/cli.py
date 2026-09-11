from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from .bps_webapi import discover_webapi_variables, fetch_free_publications, fetch_free_webapi_data
from .compare import compare_files
from .coverage import apply_coverage, profile_free_webapi
from .inventory import indicator_paths, load_indicators, validate_inventory


DEFAULT_SOURCE_REGISTRY = Path("config/sources/bps_sources.csv")
DEFAULT_INDICATOR_DIR = Path("config/indicators")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_coverage_manifest(args: argparse.Namespace, result: dict) -> None:
    inputs = [args.manifest, args.selection, args.publication_selection, *indicator_paths(args.indicator_dir)]
    outputs = []
    for path in (args.variable_output, args.indicator_output):
        with path.open(newline="", encoding="utf-8") as handle:
            rows = sum(1 for _ in csv.DictReader(handle))
        outputs.append({"path": str(path), "rows": rows, "sha256": _sha256(path)})
    manifest = {
        "stage": "H1",
        "track": "coverage",
        "coverage_status": "profiled",
        "minimum_span": args.minimum_span,
        "statuses": dict(sorted(result["statuses"].items())),
        "inputs": [{"path": str(path), "sha256": _sha256(path)} for path in inputs],
        "outputs": outputs,
    }
    args.coverage_manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.coverage_manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


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

    discover = subparsers.add_parser("discover-webapi")
    discover.add_argument("--domain", default="0000")
    discover.add_argument("--workers", type=int, default=4)
    discover.add_argument("--top", type=int, default=5)
    discover.add_argument("--env-file", type=Path, default=Path(".env"))
    discover.add_argument("--raw-output", type=Path, default=Path("data/raw/h1/webapi-variables-0000.json"))
    discover.add_argument(
        "--candidate-output",
        type=Path,
        default=Path("results/processed/h1-webapi-candidates.csv"),
    )
    discover.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h1-webapi-variable-catalog.json"),
    )

    fetch = subparsers.add_parser("fetch-free-webapi")
    fetch.add_argument(
        "--selection",
        type=Path,
        default=Path("config/sources/free_webapi_selection.csv"),
    )
    fetch.add_argument("--env-file", type=Path, default=Path(".env"))
    fetch.add_argument("--raw-dir", type=Path, default=Path("data/raw/h1/webapi"))
    fetch.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h1-free-webapi-data.json"),
    )
    fetch.add_argument("--since-year", type=int, default=2015)
    fetch.add_argument("--workers", type=int, default=4)

    publications = subparsers.add_parser("fetch-free-publications")
    publications.add_argument("--env-file", type=Path, default=Path(".env"))
    publications.add_argument(
        "--raw-dir", type=Path, default=Path("data/raw/h1/publications")
    )
    publications.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h1-free-publications.json"),
    )

    profile = subparsers.add_parser("profile-coverage")
    profile.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/h1-free-webapi-data.json"),
    )
    profile.add_argument(
        "--selection",
        type=Path,
        default=Path("config/sources/free_webapi_selection.csv"),
    )
    profile.add_argument(
        "--publication-selection",
        type=Path,
        default=Path("config/sources/free_publication_selection.csv"),
    )
    profile.add_argument("--indicator-dir", type=Path, default=DEFAULT_INDICATOR_DIR)
    profile.add_argument(
        "--variable-output",
        type=Path,
        default=Path("results/processed/h1-webapi-coverage.csv"),
    )
    profile.add_argument(
        "--indicator-output",
        type=Path,
        default=Path("results/processed/h1-indicator-coverage.csv"),
    )
    profile.add_argument("--minimum-span", type=int, default=8)
    profile.add_argument(
        "--coverage-manifest-output",
        type=Path,
        default=Path("data/manifests/h1-coverage.json"),
    )

    apply_command = subparsers.add_parser("apply-coverage")
    apply_command.add_argument(
        "--indicator-coverage",
        type=Path,
        default=Path("results/processed/h1-indicator-coverage.csv"),
    )
    apply_command.add_argument("--indicator-dir", type=Path, default=DEFAULT_INDICATOR_DIR)
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

    if args.command == "discover-webapi":
        result = discover_webapi_variables(
            domain=args.domain,
            indicator_dir=DEFAULT_INDICATOR_DIR,
            env_file=args.env_file,
            raw_output=args.raw_output,
            candidate_output=args.candidate_output,
            manifest_output=args.manifest_output,
            workers=args.workers,
            top=args.top,
        )
        print(
            f"Fetched {result['variable_count']} variables from domain {args.domain}; "
            f"wrote {result['candidate_count']} candidates to {args.candidate_output}"
        )
        print(f"Raw catalog: {args.raw_output}")
        print(f"Manifest: {args.manifest_output}")
        return 0

    if args.command == "fetch-free-webapi":
        result = fetch_free_webapi_data(
            selection_path=args.selection,
            env_file=args.env_file,
            raw_dir=args.raw_dir,
            manifest_output=args.manifest_output,
            workers=args.workers,
            since_year=args.since_year,
        )
        print(
            f"Fetched {result['variable_count']} free WebAPI variables, "
            f"{result['period_count']} periods, and {result['cell_count']} data cells"
        )
        print(f"Manifest: {args.manifest_output}")
        return 0

    if args.command == "fetch-free-publications":
        result = fetch_free_publications(
            env_file=args.env_file,
            raw_dir=args.raw_dir,
            manifest_output=args.manifest_output,
        )
        print(
            f"Fetched {result['publication_count']} free BPS publications "
            f"({result['byte_count']} bytes)"
        )
        print(f"Manifest: {args.manifest_output}")
        return 0

    if args.command == "profile-coverage":
        result = profile_free_webapi(
            manifest_path=args.manifest,
            selection_path=args.selection,
            publication_selection_path=args.publication_selection,
            indicator_dir=args.indicator_dir,
            variable_output=args.variable_output,
            indicator_output=args.indicator_output,
            minimum_span=args.minimum_span,
        )
        print(
            f"Profiled {result['variable_count']} WebAPI variables against "
            f"{result['indicator_count']} inventory rows"
        )
        for status, count in sorted(result["statuses"].items()):
            print(f"  {status:14} {count:2}")
        print(f"Variable coverage: {args.variable_output}")
        print(f"Indicator coverage: {args.indicator_output}")
        write_coverage_manifest(args, result)
        print(f"Manifest: {args.coverage_manifest_output}")
        return 0

    if args.command == "apply-coverage":
        result = apply_coverage(
            indicator_coverage=args.indicator_coverage,
            indicator_dir=args.indicator_dir,
        )
        print(
            f"Applied coverage for {result['indicator_count']} indicators; "
            f"{result['updated_rows']} inventory rows changed"
        )
        return 0

    output_rows = compare_files(args.input, args.output)
    counts = Counter(row["status"] for row in output_rows)
    print(f"Wrote {len(output_rows)} compared cells to {args.output}")
    for status, count in sorted(counts.items()):
        print(f"{status:16} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
