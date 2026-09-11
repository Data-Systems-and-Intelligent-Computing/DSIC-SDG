from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h6.pipeline import OBSERVATION_COLUMNS, TYPE_BY_COLUMN


STORE_ADDITIONAL_COLUMNS = ["source_id", "vintage_date", "vintage_retrieved_at", "arrival_order"]
STORE_COLUMNS = [*OBSERVATION_COLUMNS, *STORE_ADDITIONAL_COLUMNS]
DERIVED_COLUMNS = ["vintage_count", "value_revision_count", "recomputed_at_arrival"]
CURRENT_COLUMNS = [*STORE_COLUMNS, *DERIVED_COLUMNS]
RESOLUTION_COLUMNS = [*OBSERVATION_COLUMNS, "vintage_count", "value_revision_count"]
ASOF_COLUMNS = [*OBSERVATION_COLUMNS, "asof_order", "asof_vintage_id"]
IMPACT_COLUMNS = [
    "arrival_order",
    "arrival_vintage_id",
    "observation_id",
    "observation_node_id",
    "lineage_edge_id",
    "cell_node_id",
    "cell_id",
    "impact_basis",
]
ARRIVAL_COLUMNS = [
    "arrival_order",
    "vintage_id",
    "source_id",
    "vintage_date",
    "input_rows",
    "dirty_cells",
    "recomputed_cells",
    "untouched_cells",
    "full_recompute_cells",
    "inserted_cells",
    "resolved_changed_cells",
    "value_changed_cells",
    "provenance_only_cells",
    "unchanged_resolution_cells",
    "store_rows_after",
    "current_rows_after",
    "current_sha256",
    "incremental_equals_full",
]
REPRODUCIBILITY_COLUMNS = [
    "request_id",
    "cell_id",
    "requested_observation_id",
    "requested_vintage_id",
    "requested_source_id",
    "requested_vintage_date",
    "requested_value_lexeme",
    "lookup_key",
    "available_by_vintage_key",
    "result",
    "returned_observation_id",
    "returned_value_decimal",
    "returned_value_lexeme",
    "current_observation_id",
]
VALIDATION_COLUMNS = ["check_id", "status", "observed", "expected", "detail"]
SUMMARY_COLUMNS = ["metric", "value", "unit", "interpretation"]
NULLABLE_H6 = {"trace_id", "cause_family", "evidence_level"}
IMPACT_RELATIONSHIP = "observation_materializes_cell"


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
    manifest_path: Path, requirements: dict[str, str]
) -> dict[str, tuple[Path, dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in requirements.items()):
        raise ValueError(f"H9 requires a valid {manifest_path} input")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested output {path}")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested output {path}")
        outputs[path.name] = (path, item)
    return outputs


def _required(
    outputs: dict[str, tuple[Path, dict[str, Any]]], name: str
) -> tuple[Path, dict[str, Any]]:
    if name not in outputs:
        raise ValueError(f"required manifested output {name} is missing")
    return outputs[name]


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_version") != "b3.1" or contract.get("treatment_id") != "B3":
        raise ValueError("unsupported B3 contract")
    store = contract["store"]
    if store["primary_key"] != ["cell_id", "vintage_id"]:
        raise ValueError("B3 store must key observations by cell_id and vintage_id")
    if store["mutation_policy"] != "append_only_no_update_no_delete":
        raise ValueError("B3 store must be append-only")
    if store["additional_columns"] != [
        ["source_id", "STRING", False],
        ["vintage_date", "DATE", False],
        ["vintage_retrieved_at", "TIMESTAMP", False],
        ["arrival_order", "INT", False],
    ]:
        raise ValueError("B3 store columns do not match the implementation")
    serving = contract["serving"]
    if serving["primary_key"] != ["cell_id"] or serving["derived_columns"] != [
        ["vintage_count", "INT", False],
        ["value_revision_count", "INT", False],
        ["recomputed_at_arrival", "INT", False],
    ]:
        raise ValueError("B3 serving columns do not match the implementation")
    if serving["resolution_independent_of_arrival_order"] is not True:
        raise ValueError("B3 resolution must not depend on arrival order")
    impact = contract["impact_analysis"]
    if (
        impact["lineage_relationship"] != IMPACT_RELATIONSHIP
        or impact["must_equal_observation_cell_id"] is not True
        or impact["fuzzy_matching_allowed"] is not False
    ):
        raise ValueError("B3 dirty cells must come from exact H6C lineage edges")
    reproducibility = contract["reproducibility"]
    if reproducibility["addressable_key"] != ["cell_id", "vintage_id"]:
        raise ValueError("B3 must address history by cell_id and vintage_id")
    if reproducibility["depends_on_table_snapshots"] is not False:
        raise ValueError("B3 historical reads must not depend on table snapshots")
    if contract["measurement_boundary"]["physical_bytes_and_runtime"] != "deferred_to_H10":
        raise ValueError("H9 must not claim the H10 physical measurement")
    if contract["injected_workload"]["h8b_route_status"] != "prepared_not_run":
        raise ValueError("H9 tracks A and C must not claim execution of the H8B routes")


def validate_ddl(contract: dict[str, Any], ddl: str) -> None:
    normalized = " ".join(ddl.split()).upper()
    tables = {
        contract["store"]["table"]: [*contract["store"]["additional_columns"]],
        contract["serving"]["table"]: [
            *contract["store"]["additional_columns"],
            *contract["serving"]["derived_columns"],
        ],
    }
    for table, extra_columns in tables.items():
        match = re.search(
            rf"CREATE TABLE {re.escape(table.upper())} \((.*?)\) USING ICEBERG", normalized
        )
        if not match:
            raise ValueError(f"DDL does not create {table}")
        table_ddl = match.group(1)
        for name in OBSERVATION_COLUMNS:
            declaration = f"{name} {TYPE_BY_COLUMN[name]}".upper()
            if name not in NULLABLE_H6:
                declaration += " NOT NULL"
            if declaration not in table_ddl:
                raise ValueError(f"DDL declaration for {table} does not match H6 column {name}")
        for name, data_type, nullable in extra_columns:
            declaration = f"{name} {data_type}".upper()
            if not nullable:
                declaration += " NOT NULL"
            if declaration not in table_ddl:
                raise ValueError(f"DDL declaration for {table} does not match B3 column {name}")
    if normalized.count("PARTITIONED BY (DOMAIN)") != 2:
        raise ValueError("both B3 tables must partition by domain")
    store = contract["store"]["table"].upper()
    if f"UPDATE {store}" in normalized or f"DELETE FROM {store}" in normalized or f"MERGE INTO {store}" in normalized:
        raise ValueError("B3 DDL must not mutate the append-only store")


def _resolution_key(row: dict[str, str]) -> tuple[str, datetime, str]:
    return (
        row["vintage_date"],
        datetime.fromisoformat(row["vintage_retrieved_at"]),
        row["vintage_id"],
    )


def _vintage_key(vintage: dict[str, str]) -> tuple[str, datetime, str]:
    return (
        vintage["vintage_date"],
        datetime.fromisoformat(vintage["retrieved_at"]),
        vintage["vintage_id"],
    )


def resolve_cell(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        raise ValueError("cannot resolve a cell without stored vintages")
    ordered = sorted(rows, key=_resolution_key)
    revisions = sum(
        Decimal(previous["value_decimal"]) != Decimal(row["value_decimal"])
        for previous, row in zip(ordered, ordered[1:])
    )
    return {
        **ordered[-1],
        "vintage_count": str(len(ordered)),
        "value_revision_count": str(revisions),
    }


def lineage_impact_index(
    nodes: list[dict[str, str]], edges: list[dict[str, str]]
) -> dict[str, dict[str, str]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    index: dict[str, dict[str, str]] = {}
    for edge in edges:
        if edge["relationship"] != IMPACT_RELATIONSHIP:
            continue
        observation_node = node_by_id.get(edge["from_node_id"])
        cell_node = node_by_id.get(edge["to_node_id"])
        if (
            observation_node is None
            or cell_node is None
            or observation_node["node_type"] != "observation"
            or cell_node["node_type"] != "indicator_cell"
        ):
            raise ValueError(f"lineage edge {edge['edge_id']} does not join an observation to a cell")
        observation_id = observation_node["natural_key"]
        if observation_id in index:
            raise ValueError(f"lineage maps observation {observation_id} to more than one cell")
        index[observation_id] = {
            "observation_node_id": observation_node["node_id"],
            "lineage_edge_id": edge["edge_id"],
            "cell_node_id": cell_node["node_id"],
            "cell_id": cell_node["natural_key"],
        }
    return index


def simulate_vintage_aware(
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    lineage_nodes: list[dict[str, str]],
    lineage_edges: list[dict[str, str]],
    arrival_vintage_ids: list[str] | None = None,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, int],
]:
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    if len(vintage_by_id) != len(vintages):
        raise ValueError("duplicate H6 vintage_id")
    if unknown := {row["vintage_id"] for row in observations} - vintage_by_id.keys():
        raise ValueError(f"observations reference unknown vintages {sorted(unknown)}")
    ordered_vintages = sorted(vintages, key=_vintage_key)
    if arrival_vintage_ids is None:
        arrival = ordered_vintages
    else:
        if sorted(arrival_vintage_ids) != sorted(vintage_by_id):
            raise ValueError("arrival order must be a permutation of the H6 vintages")
        arrival = [vintage_by_id[vintage_id] for vintage_id in arrival_vintage_ids]
    impact_index = lineage_impact_index(lineage_nodes, lineage_edges)
    observations_by_vintage: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        observations_by_vintage[row["vintage_id"]].append(row)

    store: list[dict[str, str]] = []
    store_by_cell: dict[str, list[dict[str, str]]] = defaultdict(list)
    store_keys: set[tuple[str, str]] = set()
    stored_observations: set[str] = set()
    current: dict[str, dict[str, str]] = {}
    arrivals: list[dict[str, str]] = []
    impact_rows: list[dict[str, str]] = []

    for order, vintage in enumerate(arrival, start=1):
        incoming = sorted(
            observations_by_vintage[vintage["vintage_id"]],
            key=lambda row: (row["cell_id"], row["observation_id"]),
        )
        if not incoming:
            raise ValueError(f"vintage {vintage['vintage_id']} has no observations")
        dirty: set[str] = set()
        for row in incoming:
            key = (row["cell_id"], row["vintage_id"])
            if key in store_keys or row["observation_id"] in stored_observations:
                raise ValueError(f"B3 store already contains {key}; the store is append-only")
            impact = impact_index.get(row["observation_id"])
            if impact is None:
                raise ValueError(f"observation {row['observation_id']} has no H6C lineage edge")
            if impact["cell_id"] != row["cell_id"]:
                raise ValueError(
                    f"H6C lineage maps observation {row['observation_id']} to a different cell"
                )
            stored = {
                **{column: row[column] for column in OBSERVATION_COLUMNS},
                "source_id": vintage["source_id"],
                "vintage_date": vintage["vintage_date"],
                "vintage_retrieved_at": vintage["retrieved_at"],
                "arrival_order": str(order),
            }
            store.append(stored)
            store_by_cell[row["cell_id"]].append(stored)
            store_keys.add(key)
            stored_observations.add(row["observation_id"])
            dirty.add(impact["cell_id"])
            impact_rows.append(
                {
                    "arrival_order": str(order),
                    "arrival_vintage_id": vintage["vintage_id"],
                    "observation_id": row["observation_id"],
                    **impact,
                    "impact_basis": f"exact H6C {IMPACT_RELATIONSHIP} edge",
                }
            )

        previous = dict(current)
        inserted = resolved_changed = value_changed = unchanged = 0
        for cell_id in sorted(dirty):
            resolved = resolve_cell(store_by_cell[cell_id])
            before = previous.get(cell_id)
            if before is None:
                inserted += 1
            elif before["observation_id"] != resolved["observation_id"]:
                resolved_changed += 1
                if Decimal(before["value_decimal"]) != Decimal(resolved["value_decimal"]):
                    value_changed += 1
            else:
                unchanged += 1
            current[cell_id] = {**resolved, "recomputed_at_arrival": str(order)}

        full = {cell_id: resolve_cell(rows) for cell_id, rows in store_by_cell.items()}
        incremental_equals_full = set(full) == set(current) and all(
            {column: current[cell_id][column] for column in RESOLUTION_COLUMNS}
            == {column: full[cell_id][column] for column in RESOLUTION_COLUMNS}
            for cell_id in full
        )
        if not incremental_equals_full:
            raise ValueError(f"B3 incremental state diverges from full recomputation at arrival {order}")
        current_rows = sorted(current.values(), key=lambda row: row["cell_id"])
        arrivals.append(
            {
                "arrival_order": str(order),
                "vintage_id": vintage["vintage_id"],
                "source_id": vintage["source_id"],
                "vintage_date": vintage["vintage_date"],
                "input_rows": str(len(incoming)),
                "dirty_cells": str(len(dirty)),
                "recomputed_cells": str(len(dirty)),
                "untouched_cells": str(len(current) - len(dirty)),
                "full_recompute_cells": str(len(full)),
                "inserted_cells": str(inserted),
                "resolved_changed_cells": str(resolved_changed),
                "value_changed_cells": str(value_changed),
                "provenance_only_cells": str(resolved_changed - value_changed),
                "unchanged_resolution_cells": str(unchanged),
                "store_rows_after": str(len(store)),
                "current_rows_after": str(len(current)),
                "current_sha256": _rows_sha256(CURRENT_COLUMNS, current_rows),
                "incremental_equals_full": "yes",
            }
        )

    current_state = sorted(current.values(), key=lambda row: row["cell_id"])
    asof_states: list[dict[str, str]] = []
    for asof_order, vintage in enumerate(ordered_vintages, start=1):
        bound = _vintage_key(vintage)
        for cell_id in sorted(store_by_cell):
            eligible = [row for row in store_by_cell[cell_id] if _resolution_key(row) <= bound]
            if not eligible:
                continue
            resolved = resolve_cell(eligible)
            asof_states.append(
                {
                    **{column: resolved[column] for column in OBSERVATION_COLUMNS},
                    "asof_order": str(asof_order),
                    "asof_vintage_id": vintage["vintage_id"],
                }
            )

    store_by_key = {(row["cell_id"], row["vintage_id"]): row for row in store}
    reproducibility: list[dict[str, str]] = []
    for requested in sorted(observations, key=lambda row: row["observation_id"]):
        key = (requested["cell_id"], requested["vintage_id"])
        returned = store_by_key.get(key)
        exact = (
            returned is not None
            and returned["observation_id"] == requested["observation_id"]
            and Decimal(returned["value_decimal"]) == Decimal(requested["value_decimal"])
            and returned["value_lexeme"] == requested["value_lexeme"]
        )
        serving = current[requested["cell_id"]]
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
                "lookup_key": f"cell_id={key[0]};vintage_id={key[1]}",
                "available_by_vintage_key": "yes" if exact else "no",
                "result": (
                    "current_vintage_available"
                    if exact and serving["observation_id"] == requested["observation_id"]
                    else "historical_vintage_available" if exact else "vintage_missing"
                ),
                "returned_observation_id": returned["observation_id"] if exact else "",
                "returned_value_decimal": returned["value_decimal"] if exact else "",
                "returned_value_lexeme": returned["value_lexeme"] if exact else "",
                "current_observation_id": serving["observation_id"],
            }
        )

    def total(column: str) -> int:
        return sum(int(row[column]) for row in arrivals)

    metrics = {
        "input_rows": len(observations),
        "arrival_batches": len(arrivals),
        "store_rows": len(store),
        "final_rows": len(current_state),
        "recomputed_cells": total("recomputed_cells"),
        "full_recompute_cells": total("full_recompute_cells"),
        "untouched_cells": total("untouched_cells"),
        "inserted_cells": total("inserted_cells"),
        "resolved_changed_cells": total("resolved_changed_cells"),
        "value_changed_cells": total("value_changed_cells"),
        "provenance_only_cells": total("provenance_only_cells"),
        "unchanged_resolution_cells": total("unchanged_resolution_cells"),
        "value_revisions_in_history": sum(int(row["value_revision_count"]) for row in current_state),
        "logical_materialized_rows": len(store) + len(current_state),
        "asof_rows": len(asof_states),
        "reproduction_successes": sum(row["available_by_vintage_key"] == "yes" for row in reproducibility),
        "reproduction_failures": sum(row["available_by_vintage_key"] == "no" for row in reproducibility),
    }
    if metrics["reproduction_failures"]:
        raise ValueError("B3 failed to address at least one requested vintage")
    return arrivals, store, impact_rows, current_state, asof_states, reproducibility, metrics


def _projection(rows: list[dict[str, str]], columns: list[str]) -> list[tuple[str, ...]]:
    return sorted(tuple(row[column] for column in columns) for row in rows)


def run_h9(
    *,
    contract_path: Path,
    ddl_path: Path,
    h6_manifest_path: Path,
    h6c_manifest_path: Path,
    b0_manifest_path: Path,
    b1_manifest_path: Path,
    arrival_output: Path,
    store_output: Path,
    impact_output: Path,
    current_state_output: Path,
    asof_output: Path,
    reproducibility_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_ddl(contract, ddl_path.read_text(encoding="utf-8"))

    h6_outputs = _manifest_outputs(h6_manifest_path, {"stage": "H6", "schema_status": "validated"})
    h6c_outputs = _manifest_outputs(
        h6c_manifest_path, {"stage": "H6", "track": "C", "lineage_status": "validated"}
    )
    b0_outputs = _manifest_outputs(
        b0_manifest_path, {"stage": "H7", "treatment_id": "B0", "implementation_status": "implemented"}
    )
    b1_outputs = _manifest_outputs(
        b1_manifest_path,
        {"stage": "H8", "track": "A", "treatment_id": "B1", "implementation_status": "implemented"},
    )
    vintage_path, vintage_item = _required(h6_outputs, "h6-release-vintages.csv")
    observation_path, observation_item = _required(h6_outputs, "h6-indicator-observations.csv")
    nodes_path, nodes_item = _required(h6c_outputs, "h6c-lineage-nodes.csv")
    edges_path, edges_item = _required(h6c_outputs, "h6c-lineage-edges.csv")
    b0_state_path, b0_state_item = _required(b0_outputs, "h7-b0-final-state.csv")
    b1_states_path, b1_states_item = _required(b1_outputs, "h8-b1-snapshot-states.csv")

    arrivals, store, impact_rows, current_state, asof_states, reproducibility, metrics = (
        simulate_vintage_aware(
            _read_csv(vintage_path),
            _read_csv(observation_path),
            _read_csv(nodes_path),
            _read_csv(edges_path),
        )
    )

    b0_state = _read_csv(b0_state_path)
    final_matches_b0 = _projection(current_state, OBSERVATION_COLUMNS) == _projection(
        b0_state, OBSERVATION_COLUMNS
    )
    if not final_matches_b0:
        raise ValueError("B3 serving state diverges from the B0 latest-vintage control")
    b1_states = _read_csv(b1_states_path)
    b1_projection = _projection(
        [{**row, "asof_order": row["snapshot_order"], "asof_vintage_id": row["applied_vintage_id"]} for row in b1_states],
        ASOF_COLUMNS,
    )
    asof_matches_b1 = _projection(asof_states, ASOF_COLUMNS) == b1_projection
    if not asof_matches_b1:
        raise ValueError("B3 as-of reconstruction diverges from the B1 snapshot states")
    b1_current_order = str(max(int(row["snapshot_order"]) for row in b1_states))
    final_matches_b1 = _projection(current_state, OBSERVATION_COLUMNS) == _projection(
        [row for row in b1_states if row["snapshot_order"] == b1_current_order], OBSERVATION_COLUMNS
    )
    if not final_matches_b1:
        raise ValueError("B3 serving state diverges from the B1 current snapshot")

    success_rate = Decimal(metrics["reproduction_successes"]) / Decimal(metrics["input_rows"])
    recompute_ratio = Decimal(metrics["recomputed_cells"]) / Decimal(metrics["full_recompute_cells"])
    b1_row_appearances = len(b1_states)
    validations = [
        {"check_id": "contract", "status": "passed", "observed": "b3.1", "expected": "b3.1", "detail": "B3 contract and two-table DDL agree"},
        {"check_id": "append_only_store", "status": "passed", "observed": str(metrics["store_rows"]), "expected": str(metrics["input_rows"]), "detail": "each (cell_id, vintage_id) is inserted once and never rewritten"},
        {"check_id": "lineage_dirty_cells", "status": "passed", "observed": str(len(impact_rows)), "expected": str(metrics["input_rows"]), "detail": "every arriving observation reaches exactly one cell through an H6C lineage edge"},
        {"check_id": "incremental_equals_full", "status": "passed", "observed": str(metrics["arrival_batches"]), "expected": str(metrics["arrival_batches"]), "detail": "serving state equals full recomputation after every arrival"},
        {"check_id": "recompute_scope", "status": "passed", "observed": str(metrics["recomputed_cells"]), "expected": f"<= {metrics['full_recompute_cells']}", "detail": f"{metrics['untouched_cells']} cell evaluations skipped because no lineage edge touched them"},
        {"check_id": "current_equals_b0_b1", "status": "passed", "observed": str(final_matches_b0 and final_matches_b1).lower(), "expected": "true", "detail": "same latest-vintage answer as B0 and B1"},
        {"check_id": "asof_equals_b1_snapshots", "status": "passed", "observed": str(metrics["asof_rows"]), "expected": str(b1_row_appearances), "detail": "every release state is reconstructed from vintage keys without table snapshots"},
        {"check_id": "vintage_key_reads", "status": "passed", "observed": str(metrics["reproduction_successes"]), "expected": str(metrics["input_rows"]), "detail": "all requests return the exact observation, decimal, and lexeme"},
        {"check_id": "read_failures", "status": "passed", "observed": str(metrics["reproduction_failures"]), "expected": "0", "detail": "no requested vintage is lost"},
        {"check_id": "measurement_boundary", "status": "passed", "observed": "logical_rows_and_cells_only", "expected": "physical_measurement_at_H10", "detail": "no runtime or byte claim"},
    ]
    summary = [
        {"metric": "input_observations", "value": str(metrics["input_rows"]), "unit": "rows", "interpretation": "same H6 real-revision workload as B0, B1, and B2"},
        {"metric": "arrival_batches", "value": str(metrics["arrival_batches"]), "unit": "batches", "interpretation": "TPB 2024, TPB 2025, WebAPI 2026"},
        {"metric": "store_rows", "value": str(metrics["store_rows"]), "unit": "rows", "interpretation": "append-only observations keyed by cell_id and vintage_id"},
        {"metric": "serving_rows", "value": str(metrics["final_rows"]), "unit": "rows", "interpretation": "one derived latest-vintage row per stable cell"},
        {"metric": "logical_materialized_rows", "value": str(metrics["logical_materialized_rows"]), "unit": "rows", "interpretation": f"store plus serving rows; B1 has {b1_row_appearances} row appearances; not a byte measurement"},
        {"metric": "recomputed_cells", "value": str(metrics["recomputed_cells"]), "unit": "cell_evaluations", "interpretation": "dirty cells resolved incrementally across all arrivals"},
        {"metric": "full_recompute_cells", "value": str(metrics["full_recompute_cells"]), "unit": "cell_evaluations", "interpretation": "evaluations a full recomputation after every arrival would perform"},
        {"metric": "recompute_ratio", "value": f"{recompute_ratio:.4f}", "unit": "ratio", "interpretation": "logical work ratio on the real workload; not a runtime result"},
        {"metric": "value_changed_cells", "value": str(metrics["value_changed_cells"]), "unit": "cells", "interpretation": "resolved value changed after an arrival"},
        {"metric": "provenance_only_cells", "value": str(metrics["provenance_only_cells"]), "unit": "cells", "interpretation": "newer vintage with the same numeric value"},
        {"metric": "asof_rows", "value": str(metrics["asof_rows"]), "unit": "rows", "interpretation": "release states reconstructed on demand; equal to B1 snapshots"},
        {"metric": "vintage_read_successes", "value": str(metrics["reproduction_successes"]), "unit": "requests", "interpretation": "addressable by cell_id and vintage_id"},
        {"metric": "vintage_read_failures", "value": str(metrics["reproduction_failures"]), "unit": "requests", "interpretation": "must remain zero for B3"},
        {"metric": "vintage_read_success_rate", "value": f"{success_rate:.4f}", "unit": "ratio", "interpretation": "functional result; runtime and bytes are deferred to H10"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (arrival_output, ARRIVAL_COLUMNS, arrivals),
        (store_output, STORE_COLUMNS, store),
        (impact_output, IMPACT_COLUMNS, impact_rows),
        (current_state_output, CURRENT_COLUMNS, current_state),
        (asof_output, ASOF_COLUMNS, asof_states),
        (reproducibility_output, REPRODUCIBILITY_COLUMNS, reproducibility),
        (validation_output, VALIDATION_COLUMNS, validations),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H9",
        "track": "A",
        "treatment_id": "B3",
        "implementation_status": "implemented",
        "contract_version": contract["contract_version"],
        "iceberg_targets": {
            "store": contract["store"]["table"],
            "serving": contract["serving"]["table"],
        },
        "workload": {
            "source_stage": "H6",
            "control_treatments": ["B0", "B1"],
            **metrics,
            "recompute_ratio": f"{recompute_ratio:.4f}",
            "vintage_read_success_rate": f"{success_rate:.4f}",
            "b1_logical_row_appearances": b1_row_appearances,
        },
        "reproducibility": {
            "vintage_key_supported": True,
            "depends_on_table_snapshots": False,
            "historical_reproduction_capable": True,
        },
        "measurement": {
            "logical_rows_and_recomputed_cells_recorded": True,
            "physical_bytes_and_runtime": "deferred_to_H10",
        },
        "injected_workload": contract["injected_workload"],
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(ddl_path), "sha256": _sha256(ddl_path)},
            {"path": str(h6_manifest_path), "sha256": _sha256(h6_manifest_path)},
            {"path": str(vintage_path), "rows": vintage_item["rows"], "sha256": vintage_item["sha256"]},
            {"path": str(observation_path), "rows": observation_item["rows"], "sha256": observation_item["sha256"]},
            {"path": str(h6c_manifest_path), "sha256": _sha256(h6c_manifest_path)},
            {"path": str(nodes_path), "rows": nodes_item["rows"], "sha256": nodes_item["sha256"]},
            {"path": str(edges_path), "rows": edges_item["rows"], "sha256": edges_item["sha256"]},
            {"path": str(b0_manifest_path), "sha256": _sha256(b0_manifest_path)},
            {"path": str(b0_state_path), "rows": b0_state_item["rows"], "sha256": b0_state_item["sha256"]},
            {"path": str(b1_manifest_path), "sha256": _sha256(b1_manifest_path)},
            {"path": str(b1_states_path), "rows": b1_states_item["rows"], "sha256": b1_states_item["sha256"]},
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "treatment_id": "B3",
        **metrics,
        "recompute_ratio": f"{recompute_ratio:.4f}",
        "status": "implemented",
    }
