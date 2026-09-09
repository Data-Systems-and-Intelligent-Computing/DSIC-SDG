from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_h5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KK-CIV H5 revision-trace freeze and Gate G1 decision"
    )
    parser.add_argument(
        "--h4-manifest",
        type=Path,
        default=Path("data/manifests/h4-ingestion-classification.json"),
    )
    parser.add_argument(
        "--publication-manifest",
        type=Path,
        default=Path("data/manifests/h1-free-publications.json"),
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("config/h5/evidence_decisions.csv"),
    )
    parser.add_argument(
        "--events-output",
        type=Path,
        default=Path("results/processed/h5-confirmed-events.csv"),
    )
    parser.add_argument(
        "--traces-output",
        type=Path,
        default=Path("results/processed/h5-revision-traces.csv"),
    )
    parser.add_argument(
        "--gate-output",
        type=Path,
        default=Path("results/processed/h5-gate-g1-summary.csv"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/manifests/h5-gate1.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_h5(
        h4_manifest_path=args.h4_manifest,
        publication_manifest_path=args.publication_manifest,
        evidence_path=args.evidence,
        events_output=args.events_output,
        traces_output=args.traces_output,
        gate_output=args.gate_output,
        manifest_output=args.manifest_output,
    )
    print(
        f"H5 batch {result['batch_id']} froze {result['trace_count']} traces "
        f"({result['trace_rows']} vintage rows)"
    )
    print(
        f"Confirmed core causes: {result['confirmed_core_events']}/"
        f"{result['event_rows']} ({result['confirmed_rate']}); "
        f"Gate G1={result['gate_status']}"
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

