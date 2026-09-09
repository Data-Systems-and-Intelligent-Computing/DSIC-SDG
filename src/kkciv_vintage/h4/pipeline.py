from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kkciv_vintage.h2.pipeline import OBSERVATION_COLUMNS


CORE_CAUSES = {"vintage", "methodology", "granularity"}
INGESTION_COLUMNS = ["ingestion_batch_id", "input_dataset", "domain", *OBSERVATION_COLUMNS]
INVENTORY_COLUMNS = [
    "domain",
    "input_dataset",
    "source_id",
    "release_date",
    "geo_level",
    "observation_rows",
    "indicator_count",
    "period_start",
    "period_end",
]
EVENT_COLUMNS = [
    "event_id",
    "domain",
    "event_kind",
    "indicator_key",
    "series_key",
    "observed_period",
    "geo_level",
    "geo_code",
    "unit",
    "source_values_json",
    "absolute_difference",
    "input_label",
    "rule_id",
    "classification",
    "cause_family",
    "evidence_level",
    "counts_toward_g1",
    "classification_note",
]
SUMMARY_COLUMNS = [
    "domain",
    "cause_family",
    "evidence_level",
    "event_count",
    "counts_toward_g1",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return _sha256(path)


def _decimal(value: str, context: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{context}: non-numeric value {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"{context}: non-finite value {value!r}")
    return parsed


def _manifest_outputs(manifest_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = {item["path"]: item for item in manifest["outputs"]}
    for item in outputs.values():
        path = Path(item["path"])
        if not path.exists():
            raise FileNotFoundError(f"manifested output is missing: {path}")
        actual = _sha256(path)
        if actual != item["sha256"]:
            raise ValueError(f"checksum mismatch for {path}: {actual} != {item['sha256']}")
    return outputs, manifest


def _require_manifested(
    outputs: dict[str, dict[str, Any]], path: Path, manifest_path: Path
) -> None:
    item = outputs.get(str(path))
    if item is None:
        raise ValueError(f"{path} is not declared by {manifest_path}")
    actual_rows = len(_read_csv(path))
    if actual_rows != int(item["rows"]):
        raise ValueError(f"row count mismatch for {path}: {actual_rows} != {item['rows']}")


def load_rules(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rules: dict[tuple[str, str], dict[str, str]] = {}
    rule_ids: set[str] = set()
    required_causes = CORE_CAUSES | {
        "rounding_or_presentation",
        "unclassified",
    }
    for line_number, row in enumerate(_read_csv(path), start=2):
        key = (row["input_kind"], row["input_label"])
        if key in rules:
            raise ValueError(f"{path}:{line_number}: duplicate rule key {key}")
        if row["rule_id"] in rule_ids:
            raise ValueError(f"{path}:{line_number}: duplicate rule ID {row['rule_id']}")
        if row["cause_family"] not in required_causes:
            raise ValueError(
                f"{path}:{line_number}: unknown cause family {row['cause_family']!r}"
            )
        expected = "yes" if row["cause_family"] in CORE_CAUSES else "no"
        if row["counts_toward_g1"] != expected:
            raise ValueError(
                f"{path}:{line_number}: counts_toward_g1 must be {expected!r}"
            )
        rules[key] = row
        rule_ids.add(row["rule_id"])
    return rules


def load_domains(path: Path) -> dict[str, str]:
    rows = _read_csv(path)
    mapping = {row["indicator_key"]: row["domain"] for row in rows}
    if len(mapping) != len(rows):
        raise ValueError(f"{path}: duplicate indicator key")
    return mapping


def build_ingestion(
    *,
    datasets: list[tuple[str, Path]],
    domains: dict[str, str],
    batch_id: str,
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for dataset, path in datasets:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = set(OBSERVATION_COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path}: missing observation columns {sorted(missing)}")
            for line_number, row in enumerate(reader, start=2):
                indicator = row["indicator_key"]
                if indicator not in domains:
                    raise ValueError(f"{path}:{line_number}: unmapped indicator {indicator}")
                _decimal(row["value"], f"{path}:{line_number}")
                key = (
                    dataset,
                    row["source_id"],
                    row["indicator_key"],
                    row["series_key"],
                    row["observed_period"],
                    row["geo_level"],
                    row["geo_code"],
                    row["unit"],
                    row["source_record_id"],
                )
                if key in seen:
                    raise ValueError(f"{path}:{line_number}: duplicate observation {key}")
                seen.add(key)
                output.append(
                    {
                        "ingestion_batch_id": batch_id,
                        "input_dataset": dataset,
                        "domain": domains[indicator],
                        **{column: row[column] for column in OBSERVATION_COLUMNS},
                    }
                )
    return sorted(
        output,
        key=lambda row: (
            row["input_dataset"],
            row["source_id"],
            row["indicator_key"],
            row["series_key"],
            row["observed_period"],
            row["geo_level"],
            row["geo_code"],
        ),
    )


def ingestion_inventory(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row["domain"],
            row["input_dataset"],
            row["source_id"],
            row["release_date"],
            row["geo_level"],
        )
        grouped[key].append(row)
    output: list[dict[str, str]] = []
    for key, group in sorted(grouped.items()):
        periods = sorted(row["observed_period"] for row in group)
        output.append(
            {
                "domain": key[0],
                "input_dataset": key[1],
                "source_id": key[2],
                "release_date": key[3],
                "geo_level": key[4],
                "observation_rows": str(len(group)),
                "indicator_count": str(len({row["indicator_key"] for row in group})),
                "period_start": periods[0],
                "period_end": periods[-1],
            }
        )
    return output


def _event_id(parts: tuple[str, ...]) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def _apply_rule(
    base: dict[str, str],
    *,
    input_kind: str,
    input_label: str,
    rules: dict[tuple[str, str], dict[str, str]],
) -> dict[str, str]:
    key = (input_kind, input_label)
    if key not in rules:
        raise ValueError(f"no classification rule for {key}")
    rule = rules[key]
    return {
        **base,
        "input_label": input_label,
        "rule_id": rule["rule_id"],
        "classification": rule["classification"],
        "cause_family": rule["cause_family"],
        "evidence_level": rule["evidence_level"],
        "counts_toward_g1": rule["counts_toward_g1"],
        "classification_note": rule["description"],
    }


def classify_events(
    *,
    baseline_discrepancies: Path,
    release_discrepancies: Path,
    granularity_path: Path,
    domains: dict[str, str],
    rules: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for row in _read_csv(baseline_discrepancies):
        indicator = row["indicator_key"]
        values = json.dumps(
            {
                "bps_tpb_2024": row["publication_value"],
                "bps_webapi": row["webapi_value"],
            },
            sort_keys=True,
        )
        parts = (
            "baseline_discrepancy",
            indicator,
            row["series_key"],
            row["observed_period"],
            row["geo_level"],
            row["geo_code"],
            row["unit"],
        )
        events.append(
            _apply_rule(
                {
                    "event_id": _event_id(parts),
                    "domain": domains[indicator],
                    "event_kind": "source_value_difference",
                    "indicator_key": indicator,
                    "series_key": row["series_key"],
                    "observed_period": row["observed_period"],
                    "geo_level": row["geo_level"],
                    "geo_code": row["geo_code"],
                    "unit": row["unit"],
                    "source_values_json": values,
                    "absolute_difference": row["absolute_spread"],
                },
                input_kind="baseline_discrepancy",
                input_label=row["classification"],
                rules=rules,
            )
        )

    for row in _read_csv(release_discrepancies):
        indicator = row["indicator_key"]
        if row["domain"] != domains[indicator]:
            raise ValueError(
                f"release discrepancy domain mismatch for {indicator}: "
                f"{row['domain']} != {domains[indicator]}"
            )
        values = json.loads(row["source_values_json"])
        input_label = row["candidate_classification"]
        if input_label == "release_revision_candidate":
            if (
                "bps_tpb_2024" in values
                and "bps_tpb_2025" in values
                and Decimal(values["bps_tpb_2024"]) != Decimal(values["bps_tpb_2025"])
            ):
                input_label = "published_release_change"
        parts = (
            "release_discrepancy",
            indicator,
            row["series_key"],
            row["observed_period"],
            row["geo_level"],
            row["geo_code"],
            row["unit"],
        )
        events.append(
            _apply_rule(
                {
                    "event_id": _event_id(parts),
                    "domain": row["domain"],
                    "event_kind": "release_value_difference",
                    "indicator_key": indicator,
                    "series_key": row["series_key"],
                    "observed_period": row["observed_period"],
                    "geo_level": row["geo_level"],
                    "geo_code": row["geo_code"],
                    "unit": row["unit"],
                    "source_values_json": json.dumps(values, sort_keys=True),
                    "absolute_difference": row["absolute_spread"],
                },
                input_kind="release_discrepancy",
                input_label=input_label,
                rules=rules,
            )
        )

    for row in _read_csv(granularity_path):
        gap = Decimal(row["gap_vs_unweighted_mean"])
        if gap == 0:
            continue
        indicator = row["indicator_key"]
        parts = (
            "granularity",
            row["source_id"],
            indicator,
            row["series_key"],
            row["observed_period"],
            row["unit"],
        )
        values = {
            "national": row["national_value"],
            "province_unweighted_mean": row["province_unweighted_mean"],
            "province_count": row["province_count"],
        }
        events.append(
            _apply_rule(
                {
                    "event_id": _event_id(parts),
                    "domain": domains[indicator],
                    "event_kind": "national_province_granularity",
                    "indicator_key": indicator,
                    "series_key": row["series_key"],
                    "observed_period": row["observed_period"],
                    "geo_level": "national_vs_province",
                    "geo_code": "9999",
                    "unit": row["unit"],
                    "source_values_json": json.dumps(values, sort_keys=True),
                    "absolute_difference": str(abs(gap)),
                },
                input_kind="granularity",
                input_label="national_vs_unweighted_mean",
                rules=rules,
            )
        )

    event_ids = [row["event_id"] for row in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("classification event IDs are not unique")
    return sorted(
        events,
        key=lambda row: (
            row["domain"],
            row["event_kind"],
            row["indicator_key"],
            row["observed_period"],
            row["geo_code"],
            row["event_id"],
        ),
    )


def classification_summary(events: list[dict[str, str]]) -> list[dict[str, str]]:
    counts = Counter(
        (
            row["domain"],
            row["cause_family"],
            row["evidence_level"],
            row["counts_toward_g1"],
        )
        for row in events
    )
    return [
        {
            "domain": key[0],
            "cause_family": key[1],
            "evidence_level": key[2],
            "event_count": str(count),
            "counts_toward_g1": key[3],
        }
        for key, count in sorted(counts.items())
    ]


def run_h4(
    *,
    baseline_manifest_path: Path,
    release_manifest_path: Path,
    rules_path: Path,
    domains_path: Path,
    ingestion_output: Path,
    inventory_output: Path,
    events_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    baseline_outputs, baseline_manifest = _manifest_outputs(baseline_manifest_path)
    release_outputs, release_manifest = _manifest_outputs(release_manifest_path)
    required_baseline = [
        Path("results/processed/h3-webapi-observations.csv"),
        Path("results/processed/h3-publication-observations.csv"),
        Path("results/processed/h3-discrepancies.csv"),
        Path("results/processed/h3-granularity.csv"),
    ]
    required_release = [
        Path("results/processed/h3-release-normalized-observations.csv"),
        Path("results/processed/h3-release-discrepancies.csv"),
    ]
    for path in required_baseline:
        _require_manifested(baseline_outputs, path, baseline_manifest_path)
    for path in required_release:
        _require_manifested(release_outputs, path, release_manifest_path)

    rules = load_rules(rules_path)
    domains = load_domains(domains_path)
    batch_digest = hashlib.sha256(
        (
            _sha256(baseline_manifest_path)
            + _sha256(release_manifest_path)
            + _sha256(domains_path)
        ).encode("ascii")
    ).hexdigest()
    batch_id = f"h4-{batch_digest[:16]}"
    ingestion = build_ingestion(
        datasets=[
            ("h3_province_webapi", required_baseline[0]),
            ("h3_province_publication", required_baseline[1]),
            ("h3_release_reconciliation", required_release[0]),
        ],
        domains=domains,
        batch_id=batch_id,
    )
    inventory = ingestion_inventory(ingestion)
    events = classify_events(
        baseline_discrepancies=required_baseline[2],
        release_discrepancies=required_release[1],
        granularity_path=required_baseline[3],
        domains=domains,
        rules=rules,
    )
    summary = classification_summary(events)

    core_events = sum(row["cause_family"] in CORE_CAUSES for row in events)
    confirmed_core = sum(
        row["cause_family"] in CORE_CAUSES and row["evidence_level"] == "observed"
        for row in events
    )
    total_events = len(events)
    candidate_rate = core_events / total_events if total_events else 0
    confirmed_rate = confirmed_core / total_events if total_events else 0
    threshold = Decimal("0.70")
    outputs = []
    for path, columns, rows in [
        (ingestion_output, INGESTION_COLUMNS, ingestion),
        (inventory_output, INVENTORY_COLUMNS, inventory),
        (events_output, EVENT_COLUMNS, events),
        (summary_output, SUMMARY_COLUMNS, summary),
    ]:
        outputs.append(
            {
                "path": str(path),
                "rows": len(rows),
                "sha256": _write_csv(path, columns, rows),
            }
        )

    manifest = {
        "stage": "H4",
        "batch_id": batch_id,
        "generated_from_snapshot_at": max(
            baseline_manifest["created_at"], release_manifest["created_at"]
        ),
        "policy": {
            "classification_rules": str(rules_path),
            "core_cause_families": sorted(CORE_CAUSES),
            "gate_g1_explanation_threshold": str(threshold),
            "candidate_evidence_is_reported_separately": True,
            "cost_class": "free",
        },
        "gate_g1": {
            "criterion_1_mismatch_domains": release_manifest["gate_g1"][
                "criterion_1_observed_domains"
            ],
            "criterion_1_passed": release_manifest["gate_g1"]["criterion_1_passed"],
            "criterion_2_total_events": total_events,
            "criterion_2_core_cause_events_candidate_inclusive": core_events,
            "criterion_2_candidate_inclusive_rate": f"{candidate_rate:.4f}",
            "criterion_2_candidate_inclusive_passed": Decimal(
                f"{candidate_rate:.4f}"
            )
            >= threshold,
            "criterion_2_confirmed_core_events": confirmed_core,
            "criterion_2_confirmed_rate": f"{confirmed_rate:.4f}",
            "criterion_2_confirmed_passed": Decimal(f"{confirmed_rate:.4f}")
            >= threshold,
            "criterion_3_status": "pending_H5_revision_trace_freeze",
            "overall_gate_status": "pending_H5",
        },
        "inputs": [
            {"path": str(baseline_manifest_path), "sha256": _sha256(baseline_manifest_path)},
            {"path": str(release_manifest_path), "sha256": _sha256(release_manifest_path)},
            {"path": str(rules_path), "sha256": _sha256(rules_path)},
            {"path": str(domains_path), "sha256": _sha256(domains_path)},
            *[
                {
                    "path": str(path),
                    "rows": int(baseline_outputs[str(path)]["rows"]),
                    "sha256": baseline_outputs[str(path)]["sha256"],
                }
                for path in required_baseline
            ],
            *[
                {
                    "path": str(path),
                    "rows": int(release_outputs[str(path)]["rows"]),
                    "sha256": release_outputs[str(path)]["sha256"],
                }
                for path in required_release
            ],
        ],
        "outputs": outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "batch_id": batch_id,
        "ingestion_rows": len(ingestion),
        "event_rows": len(events),
        "candidate_rate": f"{candidate_rate:.4f}",
        "confirmed_rate": f"{confirmed_rate:.4f}",
        "gate_status": manifest["gate_g1"]["overall_gate_status"],
    }
