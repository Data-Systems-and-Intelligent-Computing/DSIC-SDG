from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h6.pipeline import OBSERVATION_COLUMNS, TYPE_BY_COLUMN


OPERATION_COLUMNS = [
    "operation_order",
    "vintage_id",
    "source_id",
    "vintage_date",
    "input_rows",
    "inserted_rows",
    "overwritten_rows",
    "value_changed_rows",
    "same_value_overwrites",
    "output_rows",
    "state_sha256",
]
STATE_COLUMNS = [*OBSERVATION_COLUMNS, "applied_order", "replaced_observation_id"]
REPRODUCIBILITY_COLUMNS = [
    "request_id",
    "cell_id",
    "requested_observation_id",
    "requested_vintage_id",
    "requested_source_id",
    "requested_vintage_date",
    "requested_value_lexeme",
    "available_by_vintage",
    "result",
    "current_observation_id",
    "current_vintage_id",
    "current_source_id",
    "current_value_lexeme",
]
SUMMARY_COLUMNS = ["metric", "value", "unit", "interpretation"]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rows_sha256(columns: list[str], rows: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    digest.update(("\x1f".join(columns) + "\n").encode("utf-8"))
    for row in rows:
        digest.update(("\x1f".join(row[column] for column in columns) + "\n").encode("utf-8"))
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


def _manifested_outputs(
    manifest_path: Path,
) -> tuple[dict[str, tuple[Path, dict[str, Any]]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "H6" or manifest.get("schema_status") != "validated":
        raise ValueError("H7 requires a validated H6 schema manifest")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested H6 output {path}")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested H6 output {path}")
        outputs[path.name] = (path, item)
    required = {"h6-release-vintages.csv", "h6-indicator-observations.csv"}
    if missing := required - outputs.keys():
        raise ValueError(f"H6 manifest is missing {sorted(missing)}")
    return outputs, manifest


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_version") != "b0.1" or contract.get("treatment_id") != "B0":
        raise ValueError("unsupported B0 contract")
    state = contract["state"]
    if state["primary_key"] != ["cell_id"]:
        raise ValueError("B0 must keep one row per stable cell_id")
    if state["history_policy"] != "expire all Iceberg snapshots except the latest after the batch":
        raise ValueError("B0 must not retain queryable table snapshots")
    if contract["reproducibility"]["vintage_key_supported"] is not False:
        raise ValueError("B0 cannot claim vintage-addressable reads")
    schema = contract["schema"]
    if schema["base_columns"] != "h6_indicator_observations":
        raise ValueError("B0 must preserve every H6 observation column")
    if schema["additional_columns"] != [
        ["applied_order", "INT", False],
        ["replaced_observation_id", "STRING", True],
    ]:
        raise ValueError("B0 audit columns do not match the implementation")


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
            raise ValueError(f"DDL declaration does not match B0 column {name}")
    if "PARTITIONED BY (DOMAIN)" not in normalized:
        raise ValueError("B0 DDL must partition by domain")


def simulate_overwrite(
    vintages: list[dict[str, str]], observations: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    vintage_ids = [row["vintage_id"] for row in vintages]
    if len(vintage_ids) != len(set(vintage_ids)):
        raise ValueError("duplicate H6 vintage_id")
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    if unknown := {row["vintage_id"] for row in observations} - vintage_by_id.keys():
        raise ValueError(f"observations reference unknown vintages {sorted(unknown)}")

    ordered_vintages = sorted(
        vintages,
        key=lambda row: (row["vintage_date"], row["retrieved_at"], row["vintage_id"]),
    )
    observations_by_vintage: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        observations_by_vintage[row["vintage_id"]].append(row)
    state: dict[str, dict[str, str]] = {}
    operations: list[dict[str, str]] = []
    total_overwritten = 0
    total_changed = 0
    total_same = 0

    for order, vintage in enumerate(ordered_vintages, start=1):
        incoming = sorted(
            observations_by_vintage[vintage["vintage_id"]],
            key=lambda row: (row["cell_id"], row["observation_id"]),
        )
        if len({row["cell_id"] for row in incoming}) != len(incoming):
            raise ValueError(f"vintage {vintage['vintage_id']} contains duplicate cells")
        inserted = overwritten = changed = same = 0
        for row in incoming:
            previous = state.get(row["cell_id"])
            if previous is None:
                inserted += 1
                replaced = ""
            else:
                overwritten += 1
                replaced = previous["observation_id"]
                if Decimal(previous["value_decimal"]) == Decimal(row["value_decimal"]):
                    same += 1
                else:
                    changed += 1
            state[row["cell_id"]] = {
                **row,
                "applied_order": str(order),
                "replaced_observation_id": replaced,
            }
        total_overwritten += overwritten
        total_changed += changed
        total_same += same
        state_rows = sorted(state.values(), key=lambda row: row["cell_id"])
        operations.append(
            {
                "operation_order": str(order),
                "vintage_id": vintage["vintage_id"],
                "source_id": vintage["source_id"],
                "vintage_date": vintage["vintage_date"],
                "input_rows": str(len(incoming)),
                "inserted_rows": str(inserted),
                "overwritten_rows": str(overwritten),
                "value_changed_rows": str(changed),
                "same_value_overwrites": str(same),
                "output_rows": str(len(state_rows)),
                "state_sha256": _rows_sha256(STATE_COLUMNS, state_rows),
            }
        )

    final_state = sorted(state.values(), key=lambda row: row["cell_id"])
    reproducibility: list[dict[str, str]] = []
    for requested in sorted(observations, key=lambda row: row["observation_id"]):
        current = state[requested["cell_id"]]
        available = current["observation_id"] == requested["observation_id"]
        vintage = vintage_by_id[requested["vintage_id"]]
        reproducibility.append(
            {
                "request_id": requested["observation_id"],
                "cell_id": requested["cell_id"],
                "requested_observation_id": requested["observation_id"],
                "requested_vintage_id": requested["vintage_id"],
                "requested_source_id": vintage["source_id"],
                "requested_vintage_date": vintage["vintage_date"],
                "requested_value_lexeme": requested["value_lexeme"],
                "available_by_vintage": "yes" if available else "no",
                "result": "current_available" if available else "historical_overwritten",
                "current_observation_id": current["observation_id"],
                "current_vintage_id": current["vintage_id"],
                "current_source_id": vintage_by_id[current["vintage_id"]]["source_id"],
                "current_value_lexeme": current["value_lexeme"],
            }
        )

    metrics = {
        "input_rows": len(observations),
        "vintage_batches": len(ordered_vintages),
        "final_rows": len(final_state),
        "overwritten_rows": total_overwritten,
        "value_changed_rows": total_changed,
        "same_value_overwrites": total_same,
        "reproduction_successes": sum(
            row["available_by_vintage"] == "yes" for row in reproducibility
        ),
        "reproduction_failures": sum(
            row["available_by_vintage"] == "no" for row in reproducibility
        ),
    }
    if len({row["cell_id"] for row in final_state}) != len(final_state):
        raise ValueError("B0 final state contains duplicate cells")
    if metrics["overwritten_rows"] != metrics["reproduction_failures"]:
        raise ValueError("B0 overwrite and historical failure counts diverge")
    return operations, final_state, reproducibility, metrics


def run_h7(
    *,
    contract_path: Path,
    ddl_path: Path,
    h6_manifest_path: Path,
    operations_output: Path,
    state_output: Path,
    reproducibility_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_ddl(contract, ddl_path.read_text(encoding="utf-8"))
    outputs, h6_manifest = _manifested_outputs(h6_manifest_path)
    vintage_path, vintage_item = outputs["h6-release-vintages.csv"]
    observation_path, observation_item = outputs["h6-indicator-observations.csv"]
    vintages = _read_csv(vintage_path)
    observations = _read_csv(observation_path)
    operations, final_state, reproducibility, metrics = simulate_overwrite(
        vintages, observations
    )
    success_rate = Decimal(metrics["reproduction_successes"]) / Decimal(
        len(reproducibility)
    )
    summary = [
        {"metric": "input_observations", "value": str(metrics["input_rows"]), "unit": "rows", "interpretation": "ordered H6 real-revision workload"},
        {"metric": "vintage_batches", "value": str(metrics["vintage_batches"]), "unit": "batches", "interpretation": "TPB 2024, TPB 2025, WebAPI 2026"},
        {"metric": "final_current_rows", "value": str(metrics["final_rows"]), "unit": "rows", "interpretation": "exactly one row per stable cell"},
        {"metric": "overwritten_rows", "value": str(metrics["overwritten_rows"]), "unit": "rows", "interpretation": "prior vintage addresses removed"},
        {"metric": "value_changed_overwrites", "value": str(metrics["value_changed_rows"]), "unit": "rows", "interpretation": "incoming numeric value differs"},
        {"metric": "same_value_overwrites", "value": str(metrics["same_value_overwrites"]), "unit": "rows", "interpretation": "new vintage replaces an equal numeric value"},
        {"metric": "vintage_read_successes", "value": str(metrics["reproduction_successes"]), "unit": "requests", "interpretation": "only current observations remain addressable"},
        {"metric": "vintage_read_failures", "value": str(metrics["reproduction_failures"]), "unit": "requests", "interpretation": "historical observations unavailable by B0 design"},
        {"metric": "vintage_read_success_rate", "value": f"{success_rate:.4f}", "unit": "ratio", "interpretation": "negative-control result for P4, not a performance metric"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (operations_output, OPERATION_COLUMNS, operations),
        (state_output, STATE_COLUMNS, final_state),
        (reproducibility_output, REPRODUCIBILITY_COLUMNS, reproducibility),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H7",
        "treatment_id": "B0",
        "implementation_status": "implemented",
        "contract_version": contract["contract_version"],
        "iceberg_target": contract["state"]["table"],
        "history_policy": contract["state"]["history_policy"],
        "workload": {
            "source_stage": "H6",
            **metrics,
            "vintage_read_success_rate": f"{success_rate:.4f}",
        },
        "reproducibility": {
            "vintage_key_supported": False,
            "historical_read_expected": "failure_by_design",
            "historical_reproduction_capable": False,
        },
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(ddl_path), "sha256": _sha256(ddl_path)},
            {"path": str(h6_manifest_path), "sha256": _sha256(h6_manifest_path)},
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
        "treatment_id": "B0",
        **metrics,
        "status": manifest["implementation_status"],
    }
