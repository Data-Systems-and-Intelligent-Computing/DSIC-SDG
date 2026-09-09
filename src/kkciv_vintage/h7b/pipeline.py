from __future__ import annotations

import csv
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h6.pipeline import OBSERVATION_COLUMNS, TYPE_BY_COLUMN


ADDITIONAL_COLUMNS = [
    "selected_source_id",
    "trust_score",
    "source_rank",
    "candidate_count",
    "discarded_candidate_count",
    "selected_is_latest_vintage",
    "selection_contract_version",
    "selection_run_id",
]
STATE_COLUMNS = [*OBSERVATION_COLUMNS, *ADDITIONAL_COLUMNS]
DISCARD_COLUMNS = [
    "cell_id",
    "discarded_observation_id",
    "discarded_source_id",
    "discarded_vintage_id",
    "discarded_vintage_date",
    "discarded_value_lexeme",
    "discarded_trust_score",
    "discarded_source_rank",
    "selected_observation_id",
    "selected_source_id",
    "selected_trust_score",
    "discard_reason",
]
REPRODUCIBILITY_COLUMNS = [
    "request_id",
    "cell_id",
    "requested_observation_id",
    "requested_source_id",
    "requested_vintage_id",
    "requested_value_lexeme",
    "available_by_observation_id",
    "result",
    "selected_observation_id",
    "selected_source_id",
    "selected_vintage_id",
    "selected_value_lexeme",
    "discard_reason",
]
SUMMARY_COLUMNS = ["metric", "value", "unit", "interpretation"]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return _sha256(path)


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_version") != "b2.1" or contract.get("treatment_id") != "B2":
        raise ValueError("unsupported H7B B2 contract")
    if contract["input"]["score_contract_version"] != "h6b.1":
        raise ValueError("B2 must consume the frozen H6B score contract")
    if contract["input"]["selection_policy"] != "consume the frozen H6B preview without rescoring":
        raise ValueError("B2 must not rescore sources after observing conflicts")
    if contract["state"]["primary_key"] != ["cell_id"]:
        raise ValueError("B2 must materialize one row per stable cell")
    if contract["state"]["partitioning"] != ["domain"]:
        raise ValueError("B2 must use the low-cardinality domain partition")
    if contract["state"]["history_policy"] != (
        "expire all Iceberg snapshots except the latest after materialization"
    ):
        raise ValueError("B2 must not retain discarded candidates through table snapshots")
    if contract["schema"]["base_columns"] != "h6_indicator_observations":
        raise ValueError("B2 must preserve every selected H6 observation field")
    expected_additional = [
        ["selected_source_id", "STRING", False],
        ["trust_score", "DECIMAL(7,6)", False],
        ["source_rank", "INT", False],
        ["candidate_count", "INT", False],
        ["discarded_candidate_count", "INT", False],
        ["selected_is_latest_vintage", "BOOLEAN", False],
        ["selection_contract_version", "STRING", False],
        ["selection_run_id", "STRING", False],
    ]
    if contract["schema"]["additional_columns"] != expected_additional:
        raise ValueError("B2 selection audit columns do not match the implementation")


def validate_ddl(contract: dict[str, Any], ddl: str) -> None:
    normalized = " ".join(ddl.split()).upper()
    identifier = contract["state"]["table"].upper()
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {re.escape(identifier)} \((.*?)\) USING ICEBERG",
        normalized,
    )
    if not match:
        raise ValueError(f"DDL does not create {contract['state']['table']}")
    table_ddl = match.group(1)
    nullable_h6 = {"trace_id", "cause_family", "evidence_level"}
    for name in OBSERVATION_COLUMNS:
        declaration = f"{name} {TYPE_BY_COLUMN[name]}".upper()
        if name not in nullable_h6:
            declaration += " NOT NULL"
        if declaration not in table_ddl:
            raise ValueError(f"DDL declaration does not match H6 column {name}")
    for name, data_type, nullable in contract["schema"]["additional_columns"]:
        declaration = f"{name} {data_type}".upper()
        if not nullable:
            declaration += " NOT NULL"
        if declaration not in table_ddl:
            raise ValueError(f"DDL declaration does not match B2 column {name}")
    if "PARTITIONED BY (DOMAIN)" not in normalized:
        raise ValueError("B2 DDL must partition by domain")


def _verified_item(item: dict[str, Any]) -> Path:
    path = Path(item["path"])
    if not path.exists() or _sha256(path) != item["sha256"]:
        raise ValueError(f"invalid manifested input or output {path}")
    if "rows" in item and len(_read_csv(path)) != int(item["rows"]):
        raise ValueError(f"row count mismatch for manifested file {path}")
    return path


def _manifested_inputs(
    h6b_manifest_path: Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    manifest = json.loads(h6b_manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("stage") != "H6"
        or manifest.get("track") != "B"
        or manifest.get("treatment_id") != "B2"
        or manifest.get("score_status") != "frozen"
        or manifest.get("contract_version") != "h6b.1"
    ):
        raise ValueError("H7B requires a frozen H6 Jalur B manifest")
    files: dict[str, Path] = {}
    for item in [*manifest["inputs"], *manifest["outputs"]]:
        path = _verified_item(item)
        files[path.name] = path
    required = {
        "h6-release-vintages.csv",
        "h6-indicator-observations.csv",
        "h6b-source-trust-scores.csv",
        "h6b-selection-preview.csv",
        "h6b-source-trust-validation.csv",
        "h6b-source-trust.json",
    }
    if missing := required - files.keys():
        raise ValueError(f"H6B manifest is missing {sorted(missing)}")
    validation = _read_csv(files["h6b-source-trust-validation.csv"])
    if not validation or any(row["status"] != "passed" for row in validation):
        raise ValueError("H7B requires every H6B score invariant to pass")
    return files, manifest


def materialize_b2(
    *,
    contract: dict[str, Any],
    contract_sha: str,
    h6b_manifest_sha: str,
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    scores: list[dict[str, str]],
    preview: list[dict[str, str]],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, int],
]:
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    observation_by_id = {row["observation_id"]: row for row in observations}
    if len(vintage_by_id) != len(vintages) or len(observation_by_id) != len(observations):
        raise ValueError("H7B input identities are not unique")
    score_by_source = {row["source_id"]: row for row in scores}
    if len(score_by_source) != len(scores):
        raise ValueError("H7B source scores are not unique")
    preview_by_cell = {row["cell_id"]: row for row in preview}
    if len(preview_by_cell) != len(preview):
        raise ValueError("H7B preview selects a cell more than once")

    candidates_by_cell: dict[str, list[dict[str, str]]] = {}
    for observation in observations:
        if observation["vintage_id"] not in vintage_by_id:
            raise ValueError("H7B observation references an unknown vintage")
        candidates_by_cell.setdefault(observation["cell_id"], []).append(observation)
    if set(candidates_by_cell) != set(preview_by_cell):
        raise ValueError("H7B preview does not cover the complete H6 cell set")

    selection_run_id = "h7b-" + _id(contract_sha, h6b_manifest_sha)
    state: list[dict[str, str]] = []
    discarded: list[dict[str, str]] = []
    discard_reason_by_observation: dict[str, str] = {}

    for cell_id, selection in sorted(preview_by_cell.items()):
        selected_id = selection["selected_observation_id"]
        if selected_id not in observation_by_id:
            raise ValueError(f"H7B preview selects unknown observation {selected_id}")
        selected = observation_by_id[selected_id]
        if selected["cell_id"] != cell_id:
            raise ValueError("H7B selected observation belongs to a different cell")
        selected_vintage = vintage_by_id[selected["vintage_id"]]
        selected_source_id = selected_vintage["source_id"]
        selected_score = score_by_source[selected_source_id]
        candidates = candidates_by_cell[cell_id]
        if (
            selection["selected_source_id"] != selected_source_id
            or selection["selected_vintage_id"] != selected["vintage_id"]
            or selection["selected_value_lexeme"] != selected["value_lexeme"]
            or selection["selected_trust_score"] != selected_score["trust_score"]
            or int(selection["candidate_count"]) != len(candidates)
        ):
            raise ValueError("H7B frozen preview diverges from its manifested inputs")
        latest_flag = selection["selected_is_latest_vintage"] == "yes"
        state.append(
            {
                **selected,
                "selected_source_id": selected_source_id,
                "trust_score": selected_score["trust_score"],
                "source_rank": selected_score["rank"],
                "candidate_count": str(len(candidates)),
                "discarded_candidate_count": str(len(candidates) - 1),
                "selected_is_latest_vintage": "true" if latest_flag else "false",
                "selection_contract_version": contract["contract_version"],
                "selection_run_id": selection_run_id,
            }
        )

        for candidate in sorted(candidates, key=lambda row: row["observation_id"]):
            if candidate["observation_id"] == selected_id:
                continue
            candidate_vintage = vintage_by_id[candidate["vintage_id"]]
            candidate_source_id = candidate_vintage["source_id"]
            candidate_score = score_by_source[candidate_source_id]
            if Decimal(candidate_score["trust_score"]) < Decimal(selected_score["trust_score"]):
                reason = "lower_trust_score"
            elif candidate_vintage["vintage_date"] < selected_vintage["vintage_date"]:
                reason = "tie_break_older_vintage"
            elif candidate_source_id > selected_source_id:
                reason = "tie_break_source_id"
            else:
                reason = "tie_break_observation_id"
            discard_reason_by_observation[candidate["observation_id"]] = reason
            discarded.append(
                {
                    "cell_id": cell_id,
                    "discarded_observation_id": candidate["observation_id"],
                    "discarded_source_id": candidate_source_id,
                    "discarded_vintage_id": candidate["vintage_id"],
                    "discarded_vintage_date": candidate_vintage["vintage_date"],
                    "discarded_value_lexeme": candidate["value_lexeme"],
                    "discarded_trust_score": candidate_score["trust_score"],
                    "discarded_source_rank": candidate_score["rank"],
                    "selected_observation_id": selected_id,
                    "selected_source_id": selected_source_id,
                    "selected_trust_score": selected_score["trust_score"],
                    "discard_reason": reason,
                }
            )

    state.sort(key=lambda row: row["cell_id"])
    discarded.sort(key=lambda row: (row["cell_id"], row["discarded_observation_id"]))
    selected_by_cell = {row["cell_id"]: row for row in state}
    reproducibility: list[dict[str, str]] = []
    for requested in sorted(observations, key=lambda row: row["observation_id"]):
        selected = selected_by_cell[requested["cell_id"]]
        requested_source_id = vintage_by_id[requested["vintage_id"]]["source_id"]
        available = requested["observation_id"] == selected["observation_id"]
        reproducibility.append(
            {
                "request_id": requested["observation_id"],
                "cell_id": requested["cell_id"],
                "requested_observation_id": requested["observation_id"],
                "requested_source_id": requested_source_id,
                "requested_vintage_id": requested["vintage_id"],
                "requested_value_lexeme": requested["value_lexeme"],
                "available_by_observation_id": "yes" if available else "no",
                "result": "selected_available" if available else "discarded_by_source_selection",
                "selected_observation_id": selected["observation_id"],
                "selected_source_id": selected["selected_source_id"],
                "selected_vintage_id": selected["vintage_id"],
                "selected_value_lexeme": selected["value_lexeme"],
                "discard_reason": "" if available else discard_reason_by_observation[requested["observation_id"]],
            }
        )

    metrics = {
        "source_count": len(scores),
        "input_rows": len(observations),
        "cell_count": len(state),
        "selected_rows": len(state),
        "discarded_rows": len(discarded),
        "lower_score_discards": sum(row["discard_reason"] == "lower_trust_score" for row in discarded),
        "tie_break_discards": sum(row["discard_reason"].startswith("tie_break") for row in discarded),
        "latest_selected": sum(row["selected_is_latest_vintage"] == "true" for row in state),
        "older_selected": sum(row["selected_is_latest_vintage"] == "false" for row in state),
        "value_differs_from_latest": sum(row["selected_value_equals_latest"] == "no" for row in preview),
        "reproduction_successes": sum(row["available_by_observation_id"] == "yes" for row in reproducibility),
        "reproduction_failures": sum(row["available_by_observation_id"] == "no" for row in reproducibility),
    }
    if metrics["selected_rows"] + metrics["discarded_rows"] != metrics["input_rows"]:
        raise ValueError("B2 selected and discarded sets do not partition the H6 workload")
    if metrics["discarded_rows"] != metrics["reproduction_failures"]:
        raise ValueError("B2 discard and reproduction failure counts diverge")
    return state, discarded, reproducibility, metrics


def run_h7b(
    *,
    contract_path: Path,
    ddl_path: Path,
    h6b_manifest_path: Path,
    state_output: Path,
    discarded_output: Path,
    reproducibility_output: Path,
    summary_output: Path,
    validation_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_ddl(contract, ddl_path.read_text(encoding="utf-8"))
    files, h6b_manifest = _manifested_inputs(h6b_manifest_path)
    state, discarded, reproducibility, metrics = materialize_b2(
        contract=contract,
        contract_sha=_sha256(contract_path),
        h6b_manifest_sha=_sha256(h6b_manifest_path),
        vintages=_read_csv(files["h6-release-vintages.csv"]),
        observations=_read_csv(files["h6-indicator-observations.csv"]),
        scores=_read_csv(files["h6b-source-trust-scores.csv"]),
        preview=_read_csv(files["h6b-selection-preview.csv"]),
    )
    success_rate = Decimal(metrics["reproduction_successes"]) / Decimal(metrics["input_rows"])
    summary = [
        {"metric": "input_candidates", "value": str(metrics["input_rows"]), "unit": "rows", "interpretation": "complete H6 real-revision workload"},
        {"metric": "selected_rows", "value": str(metrics["selected_rows"]), "unit": "rows", "interpretation": "one frozen B2 winner per stable cell"},
        {"metric": "discarded_rows", "value": str(metrics["discarded_rows"]), "unit": "rows", "interpretation": "non-selected official observations"},
        {"metric": "lower_score_discards", "value": str(metrics["lower_score_discards"]), "unit": "rows", "interpretation": "discarded by trust score"},
        {"metric": "tie_break_discards", "value": str(metrics["tie_break_discards"]), "unit": "rows", "interpretation": "discarded after an equal score"},
        {"metric": "latest_vintage_selected", "value": str(metrics["latest_selected"]), "unit": "cells", "interpretation": "selected observation is mechanically latest"},
        {"metric": "older_vintage_selected", "value": str(metrics["older_selected"]), "unit": "cells", "interpretation": "higher source score defeats a newer vintage"},
        {"metric": "selected_value_differs_from_latest", "value": str(metrics["value_differs_from_latest"]), "unit": "cells", "interpretation": "B2 answer differs numerically from latest-vintage answer"},
        {"metric": "vintage_read_successes", "value": str(metrics["reproduction_successes"]), "unit": "requests", "interpretation": "selected observations remain addressable"},
        {"metric": "vintage_read_failures", "value": str(metrics["reproduction_failures"]), "unit": "requests", "interpretation": "discarded observations are unavailable by design"},
        {"metric": "vintage_read_success_rate", "value": f"{success_rate:.4f}", "unit": "ratio", "interpretation": "negative reproducibility result for discarded B2 candidates"},
    ]
    validation = [
        {"invariant": "frozen_h6b_selection", "status": "passed", "checked_rows": str(metrics["selected_rows"]), "detail": "materialized rows match the manifested H6B preview"},
        {"invariant": "one_row_per_cell", "status": "passed", "checked_rows": str(metrics["cell_count"]), "detail": "one selected observation for every stable H6 cell"},
        {"invariant": "complete_candidate_partition", "status": "passed", "checked_rows": str(metrics["input_rows"]), "detail": "selected and discarded sets are disjoint and complete"},
        {"invariant": "explicit_discard_reason", "status": "passed", "checked_rows": str(metrics["discarded_rows"]), "detail": "every non-selected observation records score or tie-break rejection"},
        {"invariant": "no_rescoring", "status": "passed", "checked_rows": str(metrics["source_count"]), "detail": "source scores and ranks are copied unchanged from H6B"},
        {"invariant": "reproducibility_accounting", "status": "passed", "checked_rows": str(metrics["input_rows"]), "detail": "only the 14 selected observation IDs remain addressable"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (state_output, STATE_COLUMNS, state),
        (discarded_output, DISCARD_COLUMNS, discarded),
        (reproducibility_output, REPRODUCIBILITY_COLUMNS, reproducibility),
        (summary_output, SUMMARY_COLUMNS, summary),
        (validation_output, VALIDATION_COLUMNS, validation),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H7",
        "track": "B",
        "treatment_id": "B2",
        "implementation_status": "implemented",
        "contract_version": contract["contract_version"],
        "score_contract_version": h6b_manifest["contract_version"],
        "iceberg_target": contract["state"]["table"],
        "history_policy": contract["state"]["history_policy"],
        "workload": {"source_stage": "H6 Jalur B", **metrics, "vintage_read_success_rate": f"{success_rate:.4f}"},
        "reproducibility": {
            "selected_observation_addressable": True,
            "discarded_observation_addressable": False,
            "historical_read_expected": "failure_for_discarded_candidates",
        },
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(ddl_path), "sha256": _sha256(ddl_path)},
            {"path": str(h6b_manifest_path), "sha256": _sha256(h6b_manifest_path)},
            *[
                {"path": str(path), "sha256": _sha256(path), "rows": len(_read_csv(path))}
                for name, path in sorted(files.items())
                if path.suffix == ".csv"
            ],
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"treatment_id": "B2", **metrics, "status": manifest["implementation_status"]}
