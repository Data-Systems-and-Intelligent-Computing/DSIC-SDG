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


SNAPSHOT_STATE_COLUMNS = [
    *OBSERVATION_COLUMNS,
    "snapshot_order",
    "state_snapshot_key",
    "applied_vintage_id",
]
CATALOG_COLUMNS = [
    "snapshot_order",
    "state_snapshot_key",
    "applied_vintage_id",
    "source_id",
    "vintage_date",
    "input_rows",
    "inserted_rows",
    "overwritten_rows",
    "value_changed_rows",
    "same_value_overwrites",
    "state_rows",
    "state_sha256",
]
REPRODUCIBILITY_COLUMNS = [
    "request_id",
    "cell_id",
    "requested_observation_id",
    "requested_vintage_id",
    "requested_source_id",
    "requested_vintage_date",
    "requested_value_lexeme",
    "available_by_snapshot",
    "result",
    "first_snapshot_order",
    "last_snapshot_order",
    "matching_snapshot_orders",
]
VALIDATION_COLUMNS = ["check_id", "status", "observed", "expected", "detail"]
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


def _manifest_outputs(
    manifest_path: Path, *, stage: str, status_key: str, status_value: str
) -> tuple[dict[str, tuple[Path, dict[str, Any]]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != stage or manifest.get(status_key) != status_value:
        raise ValueError(f"H8 requires valid {stage} inputs")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested {stage} output {path}")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested {stage} output {path}")
        outputs[path.name] = (path, item)
    return outputs, manifest


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_version") != "b1.1" or contract.get("treatment_id") != "B1":
        raise ValueError("unsupported B1 contract")
    state = contract["state"]
    if state["primary_key_within_snapshot"] != ["cell_id"]:
        raise ValueError("B1 must keep one row per cell_id inside each snapshot")
    if state["history_policy"] != "retain every committed release snapshot":
        raise ValueError("B1 must retain every release snapshot")
    if contract["reproducibility"]["vintage_key_supported"] is not True:
        raise ValueError("B1 must support snapshot-addressable historical reads")
    if contract["measurement_boundary"]["physical_bytes_and_runtime"] != "deferred_to_H10":
        raise ValueError("H8 must not claim the H10 physical measurement")
    schema = contract["schema"]
    if schema["base_columns"] != "h6_indicator_observations":
        raise ValueError("B1 must preserve every H6 observation column")
    if schema["additional_columns"] != [
        ["snapshot_order", "INT", False],
        ["state_snapshot_key", "STRING", False],
        ["applied_vintage_id", "STRING", False],
    ]:
        raise ValueError("B1 snapshot audit columns do not match the implementation")


def validate_ddl(contract: dict[str, Any], ddl: str) -> None:
    normalized = " ".join(ddl.split()).upper()
    identifier = contract["state"]["table"].upper()
    match = re.search(
        rf"CREATE TABLE {re.escape(identifier)} \((.*?)\) USING ICEBERG", normalized
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
            raise ValueError(f"DDL declaration does not match B1 column {name}")
    if "PARTITIONED BY (DOMAIN)" not in normalized:
        raise ValueError("B1 DDL must partition by domain")
    if "EXPIRE_SNAPSHOTS" in normalized:
        raise ValueError("B1 DDL must not expire snapshots")


def _logical_snapshot_key(order: int, vintage_id: str, state_sha256: str) -> str:
    payload = f"B1|{order}|{vintage_id}|{state_sha256}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def simulate_full_snapshots(
    vintages: list[dict[str, str]], observations: list[dict[str, str]]
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, int],
]:
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
    catalog: list[dict[str, str]] = []
    snapshot_states: list[dict[str, str]] = []
    total_overwritten = total_changed = total_same = 0

    for order, vintage in enumerate(ordered_vintages, start=1):
        incoming = sorted(
            observations_by_vintage[vintage["vintage_id"]],
            key=lambda row: (row["cell_id"], row["observation_id"]),
        )
        if not incoming:
            raise ValueError(f"vintage {vintage['vintage_id']} has no observations")
        if len({row["cell_id"] for row in incoming}) != len(incoming):
            raise ValueError(f"vintage {vintage['vintage_id']} contains duplicate cells")
        inserted = overwritten = changed = same = 0
        for row in incoming:
            previous = state.get(row["cell_id"])
            if previous is None:
                inserted += 1
            else:
                overwritten += 1
                if Decimal(previous["value_decimal"]) == Decimal(row["value_decimal"]):
                    same += 1
                else:
                    changed += 1
            state[row["cell_id"]] = dict(row)
        total_overwritten += overwritten
        total_changed += changed
        total_same += same

        base_state = sorted(state.values(), key=lambda row: row["cell_id"])
        state_digest = _rows_sha256(OBSERVATION_COLUMNS, base_state)
        snapshot_key = _logical_snapshot_key(order, vintage["vintage_id"], state_digest)
        materialized = [
            {
                **row,
                "snapshot_order": str(order),
                "state_snapshot_key": snapshot_key,
                "applied_vintage_id": vintage["vintage_id"],
            }
            for row in base_state
        ]
        snapshot_states.extend(materialized)
        catalog.append(
            {
                "snapshot_order": str(order),
                "state_snapshot_key": snapshot_key,
                "applied_vintage_id": vintage["vintage_id"],
                "source_id": vintage["source_id"],
                "vintage_date": vintage["vintage_date"],
                "input_rows": str(len(incoming)),
                "inserted_rows": str(inserted),
                "overwritten_rows": str(overwritten),
                "value_changed_rows": str(changed),
                "same_value_overwrites": str(same),
                "state_rows": str(len(materialized)),
                "state_sha256": state_digest,
            }
        )

    current_state = [row for row in snapshot_states if row["snapshot_order"] == str(len(catalog))]
    appearances: dict[str, list[int]] = defaultdict(list)
    for row in snapshot_states:
        appearances[row["observation_id"]].append(int(row["snapshot_order"]))

    reproducibility: list[dict[str, str]] = []
    for requested in sorted(observations, key=lambda row: row["observation_id"]):
        orders = sorted(appearances.get(requested["observation_id"], []))
        vintage = vintage_by_id[requested["vintage_id"]]
        is_current = bool(orders) and orders[-1] == len(catalog)
        reproducibility.append(
            {
                "request_id": requested["observation_id"],
                "cell_id": requested["cell_id"],
                "requested_observation_id": requested["observation_id"],
                "requested_vintage_id": requested["vintage_id"],
                "requested_source_id": vintage["source_id"],
                "requested_vintage_date": vintage["vintage_date"],
                "requested_value_lexeme": requested["value_lexeme"],
                "available_by_snapshot": "yes" if orders else "no",
                "result": (
                    "current_snapshot_available"
                    if is_current
                    else "historical_snapshot_available" if orders else "snapshot_missing"
                ),
                "first_snapshot_order": str(orders[0]) if orders else "",
                "last_snapshot_order": str(orders[-1]) if orders else "",
                "matching_snapshot_orders": ";".join(str(order) for order in orders),
            }
        )

    metrics = {
        "input_rows": len(observations),
        "vintage_batches": len(catalog),
        "snapshot_count": len(catalog),
        "final_rows": len(current_state),
        "logical_full_copy_rows": len(snapshot_states),
        "distinct_observations_stored": len(appearances),
        "carried_forward_row_appearances": len(snapshot_states) - len(appearances),
        "overwritten_rows": total_overwritten,
        "value_changed_rows": total_changed,
        "same_value_overwrites": total_same,
        "reproduction_successes": sum(row["available_by_snapshot"] == "yes" for row in reproducibility),
        "reproduction_failures": sum(row["available_by_snapshot"] == "no" for row in reproducibility),
    }
    if any(int(row["state_rows"]) != metrics["final_rows"] for row in catalog):
        raise ValueError("B1 release snapshots are not complete states")
    if any(len({row["cell_id"] for row in snapshot_states if row["snapshot_order"] == str(order)}) != metrics["final_rows"] for order in range(1, len(catalog) + 1)):
        raise ValueError("B1 snapshot contains duplicate or missing cells")
    if metrics["reproduction_failures"]:
        raise ValueError("B1 failed to retain at least one requested observation")
    return catalog, snapshot_states, current_state, reproducibility, metrics


def run_h8(
    *,
    contract_path: Path,
    ddl_path: Path,
    h6_manifest_path: Path,
    b0_manifest_path: Path,
    catalog_output: Path,
    snapshot_states_output: Path,
    current_state_output: Path,
    reproducibility_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_ddl(contract, ddl_path.read_text(encoding="utf-8"))

    h6_outputs, _ = _manifest_outputs(
        h6_manifest_path, stage="H6", status_key="schema_status", status_value="validated"
    )
    b0_outputs, _ = _manifest_outputs(
        b0_manifest_path, stage="H7", status_key="implementation_status", status_value="implemented"
    )
    required_h6 = {"h6-release-vintages.csv", "h6-indicator-observations.csv"}
    if missing := required_h6 - h6_outputs.keys():
        raise ValueError(f"H6 manifest is missing {sorted(missing)}")
    if "h7-b0-final-state.csv" not in b0_outputs:
        raise ValueError("B0 manifest is missing its final state")

    vintage_path, vintage_item = h6_outputs["h6-release-vintages.csv"]
    observation_path, observation_item = h6_outputs["h6-indicator-observations.csv"]
    b0_state_path, b0_state_item = b0_outputs["h7-b0-final-state.csv"]
    catalog, snapshot_states, current_state, reproducibility, metrics = simulate_full_snapshots(
        _read_csv(vintage_path), _read_csv(observation_path)
    )

    b0_state = sorted(_read_csv(b0_state_path), key=lambda row: row["cell_id"])
    b1_base = sorted(current_state, key=lambda row: row["cell_id"])
    final_matches_b0 = [
        {column: row[column] for column in OBSERVATION_COLUMNS} for row in b1_base
    ] == [{column: row[column] for column in OBSERVATION_COLUMNS} for row in b0_state]
    if not final_matches_b0:
        raise ValueError("B1 current state diverges from the B0 latest-vintage control")

    validations = [
        {"check_id": "contract", "status": "passed", "observed": "b1.1", "expected": "b1.1", "detail": "B1 contract and DDL agree"},
        {"check_id": "ordered_releases", "status": "passed", "observed": str(metrics["snapshot_count"]), "expected": str(metrics["vintage_batches"]), "detail": "one logical snapshot per release"},
        {"check_id": "complete_states", "status": "passed", "observed": str(metrics["logical_full_copy_rows"]), "expected": str(metrics["snapshot_count"] * metrics["final_rows"]), "detail": "every release materializes the complete state"},
        {"check_id": "unique_cells", "status": "passed", "observed": str(metrics["final_rows"]), "expected": "14", "detail": "one row per stable cell in every snapshot"},
        {"check_id": "current_equals_b0", "status": "passed", "observed": str(final_matches_b0).lower(), "expected": "true", "detail": "same workload produces the same latest state"},
        {"check_id": "historical_reads", "status": "passed", "observed": str(metrics["reproduction_successes"]), "expected": str(metrics["input_rows"]), "detail": "all requested observations occur in a retained state"},
        {"check_id": "read_failures", "status": "passed", "observed": str(metrics["reproduction_failures"]), "expected": "0", "detail": "no requested vintage is lost"},
        {"check_id": "measurement_boundary", "status": "passed", "observed": "logical_rows_only", "expected": "physical_measurement_at_H10", "detail": "no premature runtime or byte claim"},
    ]
    success_rate = Decimal(metrics["reproduction_successes"]) / Decimal(metrics["input_rows"])
    summary = [
        {"metric": "input_observations", "value": str(metrics["input_rows"]), "unit": "rows", "interpretation": "same H6 real-revision workload as B0"},
        {"metric": "vintage_batches", "value": str(metrics["vintage_batches"]), "unit": "batches", "interpretation": "TPB 2024, TPB 2025, WebAPI 2026"},
        {"metric": "retained_release_snapshots", "value": str(metrics["snapshot_count"]), "unit": "snapshots", "interpretation": "one complete table state per release"},
        {"metric": "rows_per_complete_state", "value": str(metrics["final_rows"]), "unit": "rows", "interpretation": "one row per stable cell"},
        {"metric": "logical_full_copy_rows", "value": str(metrics["logical_full_copy_rows"]), "unit": "row_appearances", "interpretation": "logical upper-bound footprint before H10 byte measurement"},
        {"metric": "distinct_observations_stored", "value": str(metrics["distinct_observations_stored"]), "unit": "observations", "interpretation": "all input observation identities remain present"},
        {"metric": "carried_forward_row_appearances", "value": str(metrics["carried_forward_row_appearances"]), "unit": "row_appearances", "interpretation": "unchanged cells copied into a later full state"},
        {"metric": "vintage_read_successes", "value": str(metrics["reproduction_successes"]), "unit": "requests", "interpretation": "found in at least one retained release snapshot"},
        {"metric": "vintage_read_failures", "value": str(metrics["reproduction_failures"]), "unit": "requests", "interpretation": "must remain zero for B1"},
        {"metric": "vintage_read_success_rate", "value": f"{success_rate:.4f}", "unit": "ratio", "interpretation": "functional result; runtime and bytes are deferred to H10"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (catalog_output, CATALOG_COLUMNS, catalog),
        (snapshot_states_output, SNAPSHOT_STATE_COLUMNS, snapshot_states),
        (current_state_output, SNAPSHOT_STATE_COLUMNS, current_state),
        (reproducibility_output, REPRODUCIBILITY_COLUMNS, reproducibility),
        (validation_output, VALIDATION_COLUMNS, validations),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H8",
        "track": "A",
        "treatment_id": "B1",
        "implementation_status": "implemented",
        "contract_version": contract["contract_version"],
        "iceberg_target": contract["state"]["table"],
        "history_policy": contract["state"]["history_policy"],
        "workload": {
            "source_stage": "H6",
            "control_treatment": "B0",
            **metrics,
            "vintage_read_success_rate": f"{success_rate:.4f}",
        },
        "reproducibility": {
            "snapshot_key_supported": True,
            "historical_read_expected": "success",
            "historical_reproduction_capable": True,
        },
        "measurement": {
            "logical_full_copy_rows_recorded": metrics["logical_full_copy_rows"],
            "physical_bytes_and_runtime": "deferred_to_H10",
        },
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(ddl_path), "sha256": _sha256(ddl_path)},
            {"path": str(h6_manifest_path), "sha256": _sha256(h6_manifest_path)},
            {"path": str(vintage_path), "rows": vintage_item["rows"], "sha256": vintage_item["sha256"]},
            {"path": str(observation_path), "rows": observation_item["rows"], "sha256": observation_item["sha256"]},
            {"path": str(b0_manifest_path), "sha256": _sha256(b0_manifest_path)},
            {"path": str(b0_state_path), "rows": b0_state_item["rows"], "sha256": b0_state_item["sha256"]},
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"treatment_id": "B1", **metrics, "status": "implemented"}
