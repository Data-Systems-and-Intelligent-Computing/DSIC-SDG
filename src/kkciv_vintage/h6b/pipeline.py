from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


DIMENSION_NAMES = [
    "official_authority",
    "manifested_provenance",
    "semantic_context",
    "structured_directness",
    "workload_cell_coverage",
]
SCORE_COLUMNS = [
    "rank",
    "source_id",
    "source_channel",
    "vintage_id",
    "vintage_date",
    "candidate_rows",
    "candidate_cells",
    "workload_cells",
    *DIMENSION_NAMES,
    "trust_score",
    "eligibility",
]
SELECTION_COLUMNS = [
    "cell_id",
    "domain",
    "indicator_key",
    "series_key",
    "observed_period",
    "geo_level",
    "geo_code",
    "candidate_count",
    "selected_observation_id",
    "selected_source_id",
    "selected_vintage_id",
    "selected_vintage_date",
    "selected_value_lexeme",
    "selected_trust_score",
    "runner_up_source_id",
    "runner_up_trust_score",
    "latest_observation_id",
    "latest_source_id",
    "selected_is_latest_vintage",
    "selected_value_equals_latest",
]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]
SIX_PLACES = Decimal("0.000001")


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


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(SIX_PLACES, rounding=ROUND_HALF_UP):.6f}"


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_version") != "h6b.1" or contract.get("treatment_id") != "B2":
        raise ValueError("unsupported H6B source-trust contract")
    dimensions = contract.get("dimensions", [])
    if [item.get("name") for item in dimensions] != DIMENSION_NAMES:
        raise ValueError("H6B dimensions do not match the implementation")
    weights = [Decimal(item["weight"]) for item in dimensions]
    if any(weight <= 0 for weight in weights) or sum(weights) != Decimal("1.00"):
        raise ValueError("H6B dimension weights must be positive and sum to one")
    if contract.get("formula") != "sum(weight * dimension_value)":
        raise ValueError("H6B score formula is not deterministic")
    selection = contract["selection"]
    if selection["partition_by"] != ["cell_id"] or selection["output_rows_per_cell"] != 1:
        raise ValueError("B2 must select exactly one observation per stable cell")
    expected_order = [
        "trust_score DESC",
        "vintage_date DESC",
        "source_id ASC",
        "observation_id ASC",
    ]
    if selection["order_by"] != expected_order:
        raise ValueError("H6B tie-break order does not match the implementation")
    forbidden = set(contract.get("forbidden_score_features", []))
    required_forbidden = {
        "value_decimal",
        "value_lexeme",
        "agreement_with_other_sources",
        "cause_family",
        "evidence_level",
        "whether_the_source_wins",
    }
    if forbidden != required_forbidden:
        raise ValueError("H6B must explicitly forbid every outcome-leaking feature")


def _manifested_h6_outputs(
    manifest_path: Path,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "H6" or manifest.get("schema_status") != "validated":
        raise ValueError("H6B requires a validated H6 schema manifest")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested H6 output {path}")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested H6 output {path}")
        outputs[path.name] = (path, item)
    try:
        vintage_path, vintage_item = outputs["h6-release-vintages.csv"]
        observation_path, observation_item = outputs["h6-indicator-observations.csv"]
    except KeyError as exc:
        raise ValueError("H6 manifest lacks the vintage workload") from exc
    return vintage_path, vintage_item, observation_path, observation_item


def _source_scores(
    *,
    contract: dict[str, Any],
    registry: list[dict[str, str]],
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, Decimal]]:
    registry_by_id = {row["source_id"]: row for row in registry}
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    source_vintages: dict[str, list[dict[str, str]]] = {}
    source_rows: dict[str, list[dict[str, str]]] = {}
    for vintage in vintages:
        source_vintages.setdefault(vintage["source_id"], []).append(vintage)
    for observation in observations:
        if observation["vintage_id"] not in vintage_by_id:
            raise ValueError("H6B observation references an unknown vintage")
        source_id = vintage_by_id[observation["vintage_id"]]["source_id"]
        source_rows.setdefault(source_id, []).append(observation)

    source_ids = set(source_rows)
    if source_ids - registry_by_id.keys():
        raise ValueError("H6B workload contains a source absent from the registry")
    if any(len(source_vintages[source_id]) != 1 for source_id in source_ids):
        raise ValueError("H6B v1 expects exactly one frozen vintage per source_id")

    eligibility = contract["eligibility"]
    role_map = {
        key: Decimal(value)
        for key, value in next(
            item["mapping"] for item in contract["dimensions"] if item["name"] == "semantic_context"
        ).items()
    }
    format_map = {
        key: Decimal(value)
        for key, value in next(
            item["mapping"]
            for item in contract["dimensions"]
            if item["name"] == "structured_directness"
        ).items()
    }
    weights = {
        item["name"]: Decimal(item["weight"]) for item in contract["dimensions"]
    }
    workload_cells = {row["cell_id"] for row in observations}
    raw_scores: list[tuple[dict[str, str], Decimal]] = []

    for source_id in sorted(source_ids):
        profile = registry_by_id[source_id]
        if (
            profile["workflow_status"] != eligibility["workflow_status"]
            or profile["verification_status"] != eligibility["verification_status"]
            or profile["role"] not in eligibility["allowed_roles"]
        ):
            raise ValueError(f"H6B source {source_id} is not eligible under the frozen rules")
        if profile["role"] not in role_map or profile["format"] not in format_map:
            raise ValueError(f"H6B source {source_id} has an unmapped role or format")

        rows = source_rows[source_id]
        vintage = source_vintages[source_id][0]
        source_cells = {row["cell_id"] for row in rows}
        if len(source_cells) != len(rows):
            raise ValueError(f"H6B source {source_id} has duplicate candidates for a cell")
        provenance_rows = sum(
            bool(vintage["source_manifest_path"])
            and bool(vintage["source_manifest_sha256"])
            and bool(row["source_artifact_sha256"])
            and bool(row["source_record_id"])
            for row in rows
        )
        dimensions = {
            "official_authority": Decimal("1")
            if profile["publisher"] == "Badan Pusat Statistik"
            else Decimal("0"),
            "manifested_provenance": Decimal(provenance_rows) / Decimal(len(rows)),
            "semantic_context": role_map[profile["role"]],
            "structured_directness": format_map[profile["format"]],
            "workload_cell_coverage": Decimal(len(source_cells)) / Decimal(len(workload_cells)),
        }
        if any(value < 0 or value > 1 for value in dimensions.values()):
            raise ValueError(f"H6B source {source_id} has a dimension outside [0, 1]")
        score = sum(weights[name] * dimensions[name] for name in DIMENSION_NAMES)
        score = score.quantize(SIX_PLACES, rounding=ROUND_HALF_UP)
        row = {
            "source_id": source_id,
            "source_channel": vintage["source_channel"],
            "vintage_id": vintage["vintage_id"],
            "vintage_date": vintage["vintage_date"],
            "candidate_rows": str(len(rows)),
            "candidate_cells": str(len(source_cells)),
            "workload_cells": str(len(workload_cells)),
            **{name: _format_decimal(dimensions[name]) for name in DIMENSION_NAMES},
            "trust_score": _format_decimal(score),
            "eligibility": "eligible",
        }
        raw_scores.append((row, score))

    raw_scores.sort(key=lambda item: (item[0]["source_id"], item[0]["vintage_id"]))
    raw_scores.sort(key=lambda item: item[0]["vintage_date"], reverse=True)
    raw_scores.sort(key=lambda item: item[1], reverse=True)
    scores: list[dict[str, str]] = []
    score_by_source: dict[str, Decimal] = {}
    for rank, (row, score) in enumerate(raw_scores, start=1):
        scores.append({"rank": str(rank), **row})
        score_by_source[row["source_id"]] = score
    return scores, score_by_source


def _selection_preview(
    *,
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    score_by_source: dict[str, Decimal],
) -> list[dict[str, str]]:
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    by_cell: dict[str, list[dict[str, str]]] = {}
    for observation in observations:
        by_cell.setdefault(observation["cell_id"], []).append(observation)
    preview: list[dict[str, str]] = []

    for cell_id, candidates in sorted(by_cell.items()):
        enriched = [
            {
                **row,
                "source_id": vintage_by_id[row["vintage_id"]]["source_id"],
                "vintage_date": vintage_by_id[row["vintage_id"]]["vintage_date"],
                "retrieved_at": vintage_by_id[row["vintage_id"]]["retrieved_at"],
            }
            for row in candidates
        ]
        ranked = sorted(enriched, key=lambda row: (row["source_id"], row["observation_id"]))
        ranked.sort(key=lambda row: row["vintage_date"], reverse=True)
        ranked.sort(key=lambda row: score_by_source[row["source_id"]], reverse=True)
        selected = ranked[0]
        runner_up = ranked[1]
        latest = max(
            enriched,
            key=lambda row: (
                row["vintage_date"],
                row["retrieved_at"],
                row["vintage_id"],
                row["observation_id"],
            ),
        )
        preview.append(
            {
                "cell_id": cell_id,
                "domain": selected["domain"],
                "indicator_key": selected["indicator_key"],
                "series_key": selected["series_key"],
                "observed_period": selected["observed_period"],
                "geo_level": selected["geo_level"],
                "geo_code": selected["geo_code"],
                "candidate_count": str(len(ranked)),
                "selected_observation_id": selected["observation_id"],
                "selected_source_id": selected["source_id"],
                "selected_vintage_id": selected["vintage_id"],
                "selected_vintage_date": selected["vintage_date"],
                "selected_value_lexeme": selected["value_lexeme"],
                "selected_trust_score": _format_decimal(
                    score_by_source[selected["source_id"]]
                ),
                "runner_up_source_id": runner_up["source_id"],
                "runner_up_trust_score": _format_decimal(
                    score_by_source[runner_up["source_id"]]
                ),
                "latest_observation_id": latest["observation_id"],
                "latest_source_id": latest["source_id"],
                "selected_is_latest_vintage": "yes"
                if selected["observation_id"] == latest["observation_id"]
                else "no",
                "selected_value_equals_latest": "yes"
                if Decimal(selected["value_decimal"]) == Decimal(latest["value_decimal"])
                else "no",
            }
        )
    return preview


def run_h6b(
    *,
    contract_path: Path,
    h6_manifest_path: Path,
    source_registry_path: Path,
    scores_output: Path,
    selection_output: Path,
    validation_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    vintage_path, vintage_item, observation_path, observation_item = _manifested_h6_outputs(
        h6_manifest_path
    )
    vintages = _read_csv(vintage_path)
    observations = _read_csv(observation_path)
    registry = _read_csv(source_registry_path)
    scores, score_by_source = _source_scores(
        contract=contract,
        registry=registry,
        vintages=vintages,
        observations=observations,
    )
    preview = _selection_preview(
        vintages=vintages,
        observations=observations,
        score_by_source=score_by_source,
    )
    latest_selected = sum(row["selected_is_latest_vintage"] == "yes" for row in preview)
    older_selected = len(preview) - latest_selected
    selected_value_differs = sum(
        row["selected_value_equals_latest"] == "no" for row in preview
    )
    validation = [
        {"invariant": "weights_sum_to_one", "status": "passed", "checked_rows": str(len(DIMENSION_NAMES)), "detail": "five positive weights sum exactly to 1.00"},
        {"invariant": "eligible_official_sources", "status": "passed", "checked_rows": str(len(scores)), "detail": "all workload sources are active verified BPS channels"},
        {"invariant": "complete_dimension_mapping", "status": "passed", "checked_rows": str(len(scores)), "detail": "every eligible role and format maps to [0,1]"},
        {"invariant": "no_outcome_leakage", "status": "passed", "checked_rows": str(len(contract["forbidden_score_features"])), "detail": "values, agreement, causes, evidence, and winners contribute no score points"},
        {"invariant": "one_selection_per_cell", "status": "passed", "checked_rows": str(len(preview)), "detail": "deterministic score and tie-break produce one winner for every H6 cell"},
        {"invariant": "selection_is_diagnostic_only", "status": "passed", "checked_rows": str(len(preview)), "detail": f"preview exposes {older_selected} older-vintage selections without changing the frozen score"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (scores_output, SCORE_COLUMNS, scores),
        (selection_output, SELECTION_COLUMNS, preview),
        (validation_output, VALIDATION_COLUMNS, validation),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H6",
        "track": "B",
        "treatment_id": "B2",
        "score_status": "frozen",
        "contract_version": contract["contract_version"],
        "workload": {
            "source_stage": "H6 Jalur A",
            "source_count": len(scores),
            "cell_count": len(preview),
            "candidate_observations": len(observations),
        },
        "selection_preview": {
            "selected_rows": len(preview),
            "latest_vintage_selected": latest_selected,
            "older_vintage_selected": older_selected,
            "selected_value_differs_from_latest": selected_value_differs,
            "diagnostic_only": True,
        },
        "interpretation": contract["interpretation"],
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(h6_manifest_path), "sha256": _sha256(h6_manifest_path)},
            {"path": str(source_registry_path), "sha256": _sha256(source_registry_path)},
            {"path": str(vintage_path), "rows": vintage_item["rows"], "sha256": vintage_item["sha256"]},
            {"path": str(observation_path), "rows": observation_item["rows"], "sha256": observation_item["sha256"]},
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "source_count": len(scores),
        "cell_count": len(preview),
        "latest_selected": latest_selected,
        "older_selected": older_selected,
        "selected_value_differs": selected_value_differs,
        "status": manifest["score_status"],
    }
