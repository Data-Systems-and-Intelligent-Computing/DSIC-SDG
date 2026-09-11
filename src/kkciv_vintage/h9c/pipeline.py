from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h7c.pipeline import EDGE_COLUMNS, NODE_COLUMNS
from kkciv_vintage.h8c.pipeline import (
    AUDIT_COLUMNS,
    CLOSURE_COLUMNS as H8C_CLOSURE_COLUMNS,
    FIGURE_COLUMNS,
    METRIC_COLUMNS as H8C_METRIC_COLUMNS,
)


METRIC_COLUMNS = [
    "treatment_id",
    "requests",
    "serving_state_successes",
    "historical_snapshot_successes",
    "historical_vintage_key_successes",
    "failures",
    "success_rate",
    "row_audit_failures",
    "contract_result",
]
TABLE_COLUMNS = ["table_order", *METRIC_COLUMNS, "interpretation"]
CLOSURE_COLUMNS = [
    *H8C_CLOSURE_COLUMNS[: H8C_CLOSURE_COLUMNS.index("reproducibility_metric_node_id")],
    "arrival_batch_node_id",
    "arrival_recompute_edge_id",
    *H8C_CLOSURE_COLUMNS[H8C_CLOSURE_COLUMNS.index("reproducibility_metric_node_id") :],
]
IMPACT_AUDIT_COLUMNS = [
    "impact_audit_id",
    "arrival_order",
    "arrival_vintage_id",
    "observation_id",
    "observation_cell_id",
    "reported_cell_id",
    "reported_lineage_edge_id",
    "recomputed_cell_id",
    "recomputed_lineage_edge_id",
    "store_arrival_order",
    "arrival_node_id",
    "arrival_recompute_edge_id",
    "impact_match",
]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]
SUMMARY_COLUMNS = ["metric", "value", "unit", "interpretation"]
TREATMENTS = ["B0", "B1", "B2", "B3"]
INHERITED = ["B0", "B1", "B2"]
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


def _id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def _node_id(node_type: str, *parts: str) -> str:
    return f"{node_type}:{_id(node_type, *parts)}"


def _rows_digest(columns: list[str], rows: list[dict[str, str]]) -> str:
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
    manifest_path: Path, requirements: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, tuple[Path, dict[str, Any]]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in requirements.items()):
        raise ValueError(f"unexpected manifest identity in {manifest_path}")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest.get("outputs", []):
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested output {path}")
        if "rows" in item and len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested output {path}")
        outputs[path.name] = (path, item)
    return manifest, outputs


def _required_path(outputs: dict[str, tuple[Path, dict[str, Any]]], name: str) -> Path:
    if name not in outputs:
        raise ValueError(f"required manifested output {name} is missing")
    return outputs[name][0]


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h9c.1"
        or contract.get("stage") != "H9"
        or contract.get("track") != "C"
    ):
        raise ValueError("unsupported H9C contract")
    scope = contract["scope"]
    if scope["treatments"] != TREATMENTS or scope["new_treatment"] != "B3" or scope["inherited_treatments"] != INHERITED:
        raise ValueError("H9C must add B3 to the inherited B0 B1 and B2 evidence")
    if scope["requests_per_treatment"] != 38 or scope["stable_cells"] != 14:
        raise ValueError("H9C scope does not match the frozen H6 workload")
    if contract["expected_results"] != {
        "B0": {"successes": 14, "failures": 24, "success_rate": "0.3684"},
        "B1": {"successes": 38, "failures": 0, "success_rate": "1.0000"},
        "B2": {"successes": 14, "failures": 24, "success_rate": "0.3684"},
        "B3": {"successes": 38, "failures": 0, "success_rate": "1.0000"},
    }:
        raise ValueError("H9C expected treatment outcomes changed")
    audit = contract["audit_procedure"]
    if (
        audit["must_equal_h8c_procedure_checksum"] is not True
        or audit["identity_matching"] != "exact_observation_id"
        or audit["value_matching"] != ["value_decimal", "value_lexeme"]
        or audit["lineage_matching"] != "exact_h6c_source_lineage_path_id"
        or audit["unclassified_failure_allowed"] is not False
    ):
        raise ValueError("H9C audit procedure policy changed")
    impact = contract["impact_audit"]
    if (
        impact["lineage_relationship"] != IMPACT_RELATIONSHIP
        or impact["must_equal_h9a_dirty_cells"] is not True
        or impact["final_recompute_arrival_must_equal_last_dirty_arrival"] is not True
    ):
        raise ValueError("H9C must independently re-derive B3 dirty cells")
    lineage = contract["lineage"]
    if lineage["base_nodes"] != 294 or lineage["base_edges"] != 810:
        raise ValueError("H9C must extend the frozen H8C graph")
    if lineage["fuzzy_matching_allowed"] is not False:
        raise ValueError("H9C must not use fuzzy lineage matching")
    presentation = contract["presentation"]
    if presentation["figure_status"] != "figure_data_ready_not_rendered" or presentation["manuscript_figure_claimed"] is not False:
        raise ValueError("H9C must not claim a rendered manuscript figure")


def audit_impact(
    *,
    graph_nodes: list[dict[str, str]],
    graph_edges: list[dict[str, str]],
    observations: list[dict[str, str]],
    impact_rows: list[dict[str, str]],
    store: list[dict[str, str]],
    arrivals: list[dict[str, str]],
    current: list[dict[str, str]],
) -> list[dict[str, str]]:
    node_by_id = {row["node_id"]: row for row in graph_nodes}
    lineage: dict[str, tuple[str, str]] = {}
    for edge in graph_edges:
        if edge["relationship"] != IMPACT_RELATIONSHIP:
            continue
        observation_id = node_by_id[edge["from_node_id"]]["natural_key"]
        if observation_id in lineage:
            raise ValueError(f"H9C graph maps observation {observation_id} to more than one cell")
        lineage[observation_id] = (node_by_id[edge["to_node_id"]]["natural_key"], edge["edge_id"])
    cell_by_observation = {row["observation_id"]: row["cell_id"] for row in observations}
    store_by_observation = {row["observation_id"]: row for row in store}
    if set(store_by_observation) != set(cell_by_observation):
        raise ValueError("H9C B3 store does not hold exactly the H6 observations")
    reported = {row["observation_id"]: row for row in impact_rows}
    if len(reported) != len(impact_rows) or set(reported) != set(store_by_observation):
        raise ValueError("H9C every stored B3 observation needs exactly one impact row")

    audit_rows: list[dict[str, str]] = []
    dirty_by_arrival: dict[str, set[str]] = defaultdict(set)
    last_dirty_arrival: dict[str, int] = {}
    for observation_id in sorted(reported, key=lambda key: (int(reported[key]["arrival_order"]), key)):
        row = reported[observation_id]
        if observation_id not in lineage:
            raise ValueError(f"H9C graph has no lineage edge for observation {observation_id}")
        recomputed_cell, recomputed_edge = lineage[observation_id]
        stored = store_by_observation[observation_id]
        match = (
            recomputed_cell == row["cell_id"] == cell_by_observation[observation_id]
            and recomputed_edge == row["lineage_edge_id"]
            and stored["arrival_order"] == row["arrival_order"]
            and stored["vintage_id"] == row["arrival_vintage_id"]
        )
        if not match:
            raise ValueError(f"H9C impact audit disagrees with H9A for observation {observation_id}")
        order = row["arrival_order"]
        dirty_by_arrival[order].add(recomputed_cell)
        last_dirty_arrival[recomputed_cell] = max(last_dirty_arrival.get(recomputed_cell, 0), int(order))
        audit_rows.append(
            {
                "impact_audit_id": f"impact:{_id('B3', order, observation_id)}",
                "arrival_order": order,
                "arrival_vintage_id": row["arrival_vintage_id"],
                "observation_id": observation_id,
                "observation_cell_id": cell_by_observation[observation_id],
                "reported_cell_id": row["cell_id"],
                "reported_lineage_edge_id": row["lineage_edge_id"],
                "recomputed_cell_id": recomputed_cell,
                "recomputed_lineage_edge_id": recomputed_edge,
                "store_arrival_order": stored["arrival_order"],
                "impact_match": "yes",
            }
        )
    for arrival in arrivals:
        dirty = dirty_by_arrival.get(arrival["arrival_order"], set())
        if len(dirty) != int(arrival["dirty_cells"]) or len(dirty) != int(arrival["recomputed_cells"]):
            raise ValueError(f"H9C dirty cells disagree with arrival {arrival['arrival_order']}")
    if {row["cell_id"]: int(row["recomputed_at_arrival"]) for row in current} != last_dirty_arrival:
        raise ValueError("H9C serving rows were not last recomputed at their last dirty arrival")
    return audit_rows


def build_b3_audit_rows(
    *,
    observations: list[dict[str, str]],
    source_paths: list[dict[str, str]],
    inherited_audit: list[dict[str, str]],
    store: list[dict[str, str]],
    current: list[dict[str, str]],
    reported: list[dict[str, str]],
    manifest_path: str,
    manifest_sha: str,
) -> list[dict[str, str]]:
    observation_by_id = {row["observation_id"]: row for row in observations}
    source_by_observation = {row["observation_id"]: row for row in source_paths}
    if len(observation_by_id) != 38 or set(source_by_observation) != set(observation_by_id):
        raise ValueError("H9C requires 38 H6 observations with exact H6C source paths")
    for treatment_id in INHERITED:
        requested = {row["requested_observation_id"] for row in inherited_audit if row["treatment_id"] == treatment_id}
        if requested != set(observation_by_id):
            raise ValueError(f"H9C inherited {treatment_id} audit does not cover the 38 H6 observations")
    reported_by_request = {row["requested_observation_id"]: row for row in reported}
    if set(reported_by_request) != set(observation_by_id):
        raise ValueError("H9C B3 does not audit the same 38 observation IDs")
    store_by_key = {(row["cell_id"], row["vintage_id"]): row for row in store}
    if len(store_by_key) != len(store):
        raise ValueError("H9C B3 store contains a duplicate (cell_id, vintage_id)")
    current_by_cell = {row["cell_id"]: row for row in current}
    if len(current_by_cell) != 14 or len(current) != 14:
        raise ValueError("H9C B3 serving state must contain 14 unique cells")

    rows: list[dict[str, str]] = []
    for requested_id in sorted(observation_by_id):
        requested = observation_by_id[requested_id]
        source_path = source_by_observation[requested_id]
        cell_id = requested["cell_id"]
        returned = store_by_key.get((cell_id, requested["vintage_id"]))
        serving = current_by_cell[cell_id]
        available = returned is not None and returned["observation_id"] == requested_id
        is_serving = available and serving["observation_id"] == requested_id
        expected_result = (
            "current_vintage_available" if is_serving
            else "historical_vintage_available" if available else "vintage_missing"
        )
        report = reported_by_request[requested_id]
        if (
            report["available_by_vintage_key"] != ("yes" if available else "no")
            or report["result"] != expected_result
            or report["current_observation_id"] != serving["observation_id"]
        ):
            raise ValueError("H9C B3 reported result failed independent recomputation")
        identity_match = decimal_match = lexeme_match = "not_applicable"
        if available:
            identity_match = "yes" if returned["observation_id"] == requested_id else "no"
            decimal_match = "yes" if Decimal(returned["value_decimal"]) == Decimal(requested["value_decimal"]) else "no"
            lexeme_match = "yes" if returned["value_lexeme"] == requested["value_lexeme"] else "no"
            if {identity_match, decimal_match, lexeme_match} != {"yes"}:
                raise ValueError("H9C B3 successful read does not reproduce exactly")
        rows.append(
            {
                "audit_request_id": f"audit:{_id('B3', requested_id)}",
                "treatment_id": "B3",
                "cell_id": cell_id,
                "requested_observation_id": requested_id,
                "requested_vintage_id": requested["vintage_id"],
                "source_lineage_path_id": source_path["lineage_path_id"],
                "source_record_node_id": source_path["source_record_node_id"],
                "observation_node_id": source_path["observation_node_id"],
                "requested_value_decimal": requested["value_decimal"],
                "requested_value_lexeme": requested["value_lexeme"],
                "reported_result": report["result"],
                "reported_addressable": report["available_by_vintage_key"],
                "computed_addressable": "yes" if available else "no",
                "access_class": "serving_state" if is_serving else "vintage_key" if available else "unavailable",
                "lookup_locator": f"vintage_key:cell_id={cell_id};vintage_id={requested['vintage_id']}" if available else "",
                "serving_observation_id": serving["observation_id"],
                "returned_observation_id": returned["observation_id"] if available else "",
                "returned_value_decimal": returned["value_decimal"] if available else "",
                "returned_value_lexeme": returned["value_lexeme"] if available else "",
                "identity_match": identity_match,
                "decimal_match": decimal_match,
                "lexeme_match": lexeme_match,
                "failure_class": "none" if available else "unexpected_missing_vintage",
                "treatment_manifest_path": manifest_path,
                "treatment_manifest_sha256": manifest_sha,
                "audit_status": "passed" if available else "failed",
            }
        )
    return rows


def build_metrics(
    audit_rows: list[dict[str, str]],
    inherited_metrics: list[dict[str, str]],
    contract: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    inherited = {row["treatment_id"]: row for row in inherited_metrics}
    interpretations = {
        "B0": "only the current overwritten state remains addressable",
        "B1": "current and historical observations remain addressable through retained snapshots",
        "B2": "only the selected single-source observations remain addressable",
        "B3": "every observation remains addressable by cell_id and vintage_id without table snapshots",
    }
    metrics: list[dict[str, str]] = []
    table: list[dict[str, str]] = []
    figure: list[dict[str, str]] = []
    for table_order, treatment_id in enumerate(TREATMENTS, start=1):
        rows = [row for row in audit_rows if row["treatment_id"] == treatment_id]
        serving = sum(row["access_class"] == "serving_state" for row in rows)
        snapshot = sum(row["access_class"] == "historical_snapshot" for row in rows)
        vintage_key = sum(row["access_class"] == "vintage_key" for row in rows)
        failures = sum(row["computed_addressable"] == "no" for row in rows)
        successes = serving + snapshot + vintage_key
        rate = f"{Decimal(successes) / Decimal(len(rows)):.4f}"
        expected = contract["expected_results"][treatment_id]
        if successes != expected["successes"] or failures != expected["failures"] or rate != expected["success_rate"]:
            raise ValueError(f"H9C {treatment_id} metric differs from its frozen expectation")
        metric = {
            "treatment_id": treatment_id,
            "requests": str(len(rows)),
            "serving_state_successes": str(serving),
            "historical_snapshot_successes": str(snapshot),
            "historical_vintage_key_successes": str(vintage_key),
            "failures": str(failures),
            "success_rate": rate,
            "row_audit_failures": str(sum(row["audit_status"] != "passed" for row in rows)),
            "contract_result": "matched",
        }
        if treatment_id in inherited and {
            column: metric[column] for column in H8C_METRIC_COLUMNS
        } != {column: inherited[treatment_id][column] for column in H8C_METRIC_COLUMNS}:
            raise ValueError(f"H9C {treatment_id} metric differs from the H8C metric")
        metrics.append(metric)
        table.append({"table_order": str(table_order), **metric, "interpretation": interpretations[treatment_id]})
        for series_order, (series, count) in enumerate((("addressable", successes), ("unavailable", failures))):
            figure.append(
                {
                    "figure_order": str((table_order - 1) * 2 + series_order + 1),
                    "treatment_id": treatment_id,
                    "series": series,
                    "request_count": str(count),
                    "proportion": f"{Decimal(count) / Decimal(len(rows)):.4f}",
                    "label": f"{count}/{len(rows)}",
                }
            )
    return metrics, table, figure


def close_four_treatment_graph(
    *,
    base_nodes: list[dict[str, str]],
    base_edges: list[dict[str, str]],
    base_closure: list[dict[str, str]],
    audit_rows: list[dict[str, str]],
    impact_rows: list[dict[str, str]],
    arrivals: list[dict[str, str]],
    metrics: list[dict[str, str]],
    table_rows: list[dict[str, str]],
    figure_rows: list[dict[str, str]],
    h9_manifest_path: Path,
    arrival_path: Path,
    store_path: Path,
    metrics_output: Path,
    table_output: Path,
    figure_output: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    nodes = {row["node_id"]: dict(row) for row in base_nodes}
    edges = {row["edge_id"]: dict(row) for row in base_edges}
    if len(nodes) != len(base_nodes) or len(edges) != len(base_edges):
        raise ValueError("H9C base graph identities are not unique")
    nodes_by_key = {(row["node_type"], row["natural_key"]): row["node_id"] for row in base_nodes}

    def existing(node_type: str, natural_key: str) -> str:
        if (node_type, natural_key) not in nodes_by_key:
            raise ValueError(f"H9C base graph has no {node_type} {natural_key}")
        return nodes_by_key[(node_type, natural_key)]

    def node(node_type: str, natural_key: str, node_id: str, **fields: str) -> str:
        row = {column: "" for column in NODE_COLUMNS}
        row.update({"node_id": node_id, "node_type": node_type, "natural_key": natural_key, **fields})
        previous = nodes.get(node_id)
        if previous is not None and previous != row:
            raise ValueError(f"conflicting H9C node {node_id}")
        nodes[node_id] = row
        return node_id

    def edge(
        relationship: str,
        from_node_id: str,
        to_node_id: str,
        *,
        evidence_basis: str,
        treatment_id: str = "",
        observation_id: str = "",
        cell_id: str = "",
    ) -> str:
        if from_node_id not in nodes or to_node_id not in nodes:
            raise ValueError(f"H9C {relationship} edge references an unknown node")
        edge_id = f"edge:{_id(relationship, from_node_id, to_node_id)}"
        row = {
            "edge_id": edge_id,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "relationship": relationship,
            "observation_id": observation_id,
            "cell_id": cell_id,
            "evidence_basis": evidence_basis,
            "treatment_id": treatment_id,
        }
        previous = edges.get(edge_id)
        if previous is not None and previous != row:
            raise ValueError(f"conflicting H9C edge {edge_id}")
        edges[edge_id] = row
        return edge_id

    h9_sha = _sha256(h9_manifest_path)
    run_node_id = node(
        "treatment_run",
        f"B3|{h9_sha}",
        _node_id("treatment_run", "B3", h9_sha),
        label="B3 treatment run",
        path=str(h9_manifest_path),
        sha256=h9_sha,
        treatment_id="B3",
    )
    arrival_nodes: dict[str, str] = {}
    for arrival in sorted(arrivals, key=lambda row: int(row["arrival_order"])):
        order = arrival["arrival_order"]
        natural_key = f"B3|{order}|{arrival['vintage_id']}|{arrival['current_sha256']}"
        arrival_nodes[order] = node(
            "arrival_batch",
            natural_key,
            _node_id("arrival_batch", natural_key),
            label=f"B3 arrival {order}: {arrival['dirty_cells']} dirty cells",
            source_id=arrival["source_id"],
            vintage_id=arrival["vintage_id"],
            path=str(arrival_path),
            sha256=arrival["current_sha256"],
            treatment_id="B3",
            decision="incremental_recompute",
        )
        edge(
            "treatment_run_applies_arrival",
            run_node_id,
            arrival_nodes[order],
            treatment_id="B3",
            evidence_basis="B3 arrival catalog order and serving-state checksum",
        )
        edge(
            "vintage_defines_arrival",
            existing("vintage", arrival["vintage_id"]),
            arrival_nodes[order],
            treatment_id="B3",
            evidence_basis="exact H6 vintage_id of the arriving release",
        )

    recompute_edges: dict[str, str] = {}
    for impact in impact_rows:
        observation_node_id = existing("observation", impact["observation_id"])
        arrival_node_id = arrival_nodes[impact["arrival_order"]]
        edge(
            "observation_arrives_in_batch",
            observation_node_id,
            arrival_node_id,
            treatment_id="B3",
            observation_id=impact["observation_id"],
            cell_id=impact["recomputed_cell_id"],
            evidence_basis="exact observation_id and arrival_order in the append-only B3 store",
        )
        recompute_edges[impact["observation_id"]] = edge(
            "arrival_recomputes_cell",
            arrival_node_id,
            existing("indicator_cell", impact["recomputed_cell_id"]),
            treatment_id="B3",
            observation_id=impact["observation_id"],
            cell_id=impact["recomputed_cell_id"],
            evidence_basis=f"dirty through lineage {impact['recomputed_lineage_edge_id']}",
        )
        impact["arrival_node_id"] = arrival_node_id
        impact["arrival_recompute_edge_id"] = recompute_edges[impact["observation_id"]]
    arrival_by_observation = {row["observation_id"]: row["arrival_node_id"] for row in impact_rows}

    procedure_node_id = next(row["node_id"] for row in base_nodes if row["node_type"] == "audit_procedure")
    edge(
        "procedure_governs_treatment_run",
        procedure_node_id,
        run_node_id,
        treatment_id="B3",
        evidence_basis="B3 is evaluated by the same ordered audit procedure as B0 B1 and B2",
    )
    metric_nodes = {
        row["treatment_id"]: row["node_id"]
        for row in base_nodes
        if row["node_type"] == "reproducibility_metric"
    }
    if set(metric_nodes) != set(INHERITED):
        raise ValueError("H9C base graph must contain exactly the B0 B1 and B2 metric nodes")
    b3_metric = next(row for row in metrics if row["treatment_id"] == "B3")
    b3_digest = _rows_digest(METRIC_COLUMNS, [b3_metric])
    metric_nodes["B3"] = node(
        "reproducibility_metric",
        f"B3|{b3_digest}",
        _node_id("reproducibility_metric", "B3", b3_digest),
        label=f"B3 reproducibility={b3_metric['success_rate']}",
        path=str(metrics_output),
        sha256=b3_digest,
        treatment_id="B3",
        decision="aggregated_after_row_audit",
    )
    table_digest = _rows_digest(TABLE_COLUMNS, table_rows)
    table_node_id = node(
        "evidence_table",
        table_digest,
        _node_id("evidence_table", table_digest),
        label="B0-B3 reproducibility evidence table",
        path=str(table_output),
        sha256=table_digest,
        decision="audit_table_ready",
    )
    figure_digest = _rows_digest(FIGURE_COLUMNS, figure_rows)
    figure_node_id = node(
        "figure_input",
        figure_digest,
        _node_id("figure_input", figure_digest),
        label="four-treatment reproducibility figure data",
        path=str(figure_output),
        sha256=figure_digest,
        decision="figure_data_ready_not_rendered",
    )
    for treatment_id in TREATMENTS:
        edge(
            "metric_published_in_table",
            metric_nodes[treatment_id],
            table_node_id,
            treatment_id=treatment_id,
            evidence_basis="treatment metric row is copied exactly into the four-treatment table",
        )
    edge(
        "table_supplies_figure_input",
        table_node_id,
        figure_node_id,
        evidence_basis="figure data contains the same per-treatment success and failure counts",
    )

    closure_rows: list[dict[str, str]] = []
    inherited_closure = {
        (row["treatment_id"], row["requested_observation_id"]): row for row in base_closure
    }
    for audit in audit_rows:
        treatment_id = audit["treatment_id"]
        requested = audit["requested_observation_id"]
        if treatment_id in INHERITED:
            inherited = inherited_closure[(treatment_id, requested)]
            row = {
                **{column: inherited[column] for column in H8C_CLOSURE_COLUMNS},
                "arrival_batch_node_id": "",
                "arrival_recompute_edge_id": "",
            }
        else:
            cell_id = audit["cell_id"]
            decision_node_id = node(
                "treatment_decision",
                f"B3|{requested}",
                _node_id("treatment_decision", "B3", requested),
                label=f"B3:{audit['reported_result']}",
                domain=nodes[audit["observation_node_id"]]["domain"],
                vintage_id=audit["requested_vintage_id"],
                treatment_id="B3",
                observation_id=requested,
                decision=audit["reported_result"],
                addressable=audit["computed_addressable"],
            )
            output_node_id = node(
                "treatment_output",
                f"B3|{cell_id}|{requested}",
                _node_id("treatment_output", "B3", cell_id, requested),
                label=f"B3:{cell_id}:{requested}",
                domain=nodes[audit["observation_node_id"]]["domain"],
                vintage_id=audit["requested_vintage_id"],
                path=str(store_path),
                treatment_id="B3",
                observation_id=requested,
                decision="vintage_key_addressable_output",
                addressable=audit["computed_addressable"],
            )
            common = {"treatment_id": "B3", "observation_id": requested, "cell_id": cell_id}
            edge("observation_enters_treatment", audit["observation_node_id"], decision_node_id, evidence_basis="exact H6 observation_id carried by the B3 audit", **common)
            edge("treatment_run_evaluates_candidate", run_node_id, decision_node_id, evidence_basis="checksummed H9 B3 manifest and reproducibility row", **common)
            edge("decision_resolves_to_output", decision_node_id, output_node_id, evidence_basis="requested (cell_id, vintage_id) is present in the append-only B3 store", **common)
            edge("output_serves_cell", output_node_id, existing("indicator_cell", cell_id), evidence_basis="B3 output and H6C cell share the exact stable cell_id", **common)
            row = {
                "closure_id": "",
                "treatment_id": "B3",
                "audit_request_id": audit["audit_request_id"],
                "requested_observation_id": requested,
                "source_lineage_path_id": audit["source_lineage_path_id"],
                "source_record_node_id": audit["source_record_node_id"],
                "observation_node_id": audit["observation_node_id"],
                "treatment_run_node_id": run_node_id,
                "treatment_decision_node_id": decision_node_id,
                "treatment_output_node_id": output_node_id,
                "snapshot_state_node_ids": "",
                "arrival_batch_node_id": arrival_by_observation[requested],
                "arrival_recompute_edge_id": recompute_edges[requested],
                "reproducibility_metric_node_id": metric_nodes["B3"],
                "audit_procedure_node_id": procedure_node_id,
                "complete": "yes",
            }
            edge("audit_decision_contributes_to_metric", decision_node_id, metric_nodes["B3"], evidence_basis="row-level identity value and lineage checks pass before aggregation", **common)
        row["closure_id"] = f"closure:{_id('h9c', treatment_id, requested)}"
        row["evidence_table_node_id"] = table_node_id
        row["figure_input_node_id"] = figure_node_id
        if row["reproducibility_metric_node_id"] != metric_nodes[treatment_id]:
            raise ValueError(f"H9C {treatment_id} closure points to the wrong metric node")
        closure_rows.append(row)

    node_rows = sorted(nodes.values(), key=lambda row: (row["node_type"], row["node_id"]))
    edge_rows = sorted(edges.values(), key=lambda row: (row["relationship"], row["edge_id"]))
    closure_rows.sort(key=lambda row: (TREATMENTS.index(row["treatment_id"]), row["requested_observation_id"]))
    edge_pairs = {(row["from_node_id"], row["to_node_id"]) for row in edge_rows}
    for row in closure_rows:
        reachable = (row["reproducibility_metric_node_id"], table_node_id) in edge_pairs and (
            table_node_id,
            figure_node_id,
        ) in edge_pairs
        if row["complete"] != "yes" or not reachable:
            raise ValueError("H9C evidence closure is incomplete")
    return node_rows, edge_rows, closure_rows, impact_rows, {
        "base_nodes": len(base_nodes),
        "base_edges": len(base_edges),
        "closed_nodes": len(node_rows),
        "closed_edges": len(edge_rows),
        "closure_paths": len(closure_rows),
    }


def run_h9c(
    *,
    contract_path: Path,
    procedure_path: Path,
    h6_manifest_path: Path,
    h6c_manifest_path: Path,
    h8c_manifest_path: Path,
    h9_manifest_path: Path,
    audit_output: Path,
    impact_audit_output: Path,
    metrics_output: Path,
    table_output: Path,
    figure_output: Path,
    nodes_output: Path,
    edges_output: Path,
    closure_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)

    _, h6_outputs = _manifested_outputs(h6_manifest_path, {"stage": "H6", "schema_status": "validated"})
    _, h6c_outputs = _manifested_outputs(
        h6c_manifest_path, {"stage": "H6", "track": "C", "lineage_status": "validated"}
    )
    h8c_manifest, h8c_outputs = _manifested_outputs(
        h8c_manifest_path, {"stage": "H8", "track": "C", "evidence_status": "validated"}
    )
    _, h9_outputs = _manifested_outputs(
        h9_manifest_path,
        {"stage": "H9", "track": "A", "treatment_id": "B3", "implementation_status": "implemented"},
    )
    frozen_procedure = [
        item["sha256"]
        for item in h8c_manifest["inputs"]
        if Path(item["path"]).name == Path(contract["audit_procedure"]["path"]).name
    ]
    procedure_sha = _sha256(procedure_path)
    if frozen_procedure != [procedure_sha]:
        raise ValueError("H9C audit procedure differs from the procedure frozen by H8C")
    procedure = _read_csv(procedure_path)
    owners = Counter(row["automation_owner"] for row in procedure)

    observations = _read_csv(_required_path(h6_outputs, "h6-indicator-observations.csv"))
    source_paths = _read_csv(_required_path(h6c_outputs, "h6c-cell-source-paths.csv"))
    base_nodes = _read_csv(_required_path(h8c_outputs, "h8c-lineage-nodes.csv"))
    base_edges = _read_csv(_required_path(h8c_outputs, "h8c-lineage-edges.csv"))
    base_closure = _read_csv(_required_path(h8c_outputs, "h8c-evidence-closure.csv"))
    inherited_audit = _read_csv(_required_path(h8c_outputs, "h8c-reproducibility-audit.csv"))
    inherited_metrics = _read_csv(_required_path(h8c_outputs, "h8c-reproducibility-metrics.csv"))
    arrival_path = _required_path(h9_outputs, "h9-b3-arrival-catalog.csv")
    store_path = _required_path(h9_outputs, "h9-b3-observation-store.csv")
    arrivals = _read_csv(arrival_path)
    store = _read_csv(store_path)
    impact = _read_csv(_required_path(h9_outputs, "h9-b3-impact.csv"))
    current = _read_csv(_required_path(h9_outputs, "h9-b3-current-state.csv"))
    reported = _read_csv(_required_path(h9_outputs, "h9-b3-reproducibility.csv"))

    if Counter(row["treatment_id"] for row in inherited_audit) != Counter({treatment: 38 for treatment in INHERITED}):
        raise ValueError("H9C requires the 114 inherited H8C audit rows")
    impact_rows = audit_impact(
        graph_nodes=base_nodes,
        graph_edges=base_edges,
        observations=observations,
        impact_rows=impact,
        store=store,
        arrivals=arrivals,
        current=current,
    )
    b3_audit = build_b3_audit_rows(
        observations=observations,
        source_paths=source_paths,
        inherited_audit=inherited_audit,
        store=store,
        current=current,
        reported=reported,
        manifest_path=str(h9_manifest_path),
        manifest_sha=_sha256(h9_manifest_path),
    )
    audit_rows = [*inherited_audit, *b3_audit]
    metrics, table_rows, figure_rows = build_metrics(audit_rows, inherited_metrics, contract)
    nodes, edges, closure_rows, impact_rows, graph_metrics = close_four_treatment_graph(
        base_nodes=base_nodes,
        base_edges=base_edges,
        base_closure=base_closure,
        audit_rows=audit_rows,
        impact_rows=impact_rows,
        arrivals=arrivals,
        metrics=metrics,
        table_rows=table_rows,
        figure_rows=figure_rows,
        h9_manifest_path=h9_manifest_path,
        arrival_path=arrival_path,
        store_path=store_path,
        metrics_output=metrics_output,
        table_output=table_output,
        figure_output=figure_output,
    )
    addressable = sum(row["computed_addressable"] == "yes" for row in audit_rows)
    unavailable = len(audit_rows) - addressable
    b3_addressable = sum(row["computed_addressable"] == "yes" for row in b3_audit)
    completeness = sum(row["complete"] == "yes" for row in closure_rows) / len(closure_rows)
    impact_mismatches = sum(row["impact_match"] != "yes" for row in impact_rows)
    new_nodes = Counter(row["node_type"] for row in nodes) - Counter(row["node_type"] for row in base_nodes)
    new_edges = Counter(row["relationship"] for row in edges) - Counter(row["relationship"] for row in base_edges)
    validation = [
        {"invariant": "h9c_contract", "status": "passed", "checked_rows": "7", "detail": "scope audit impact lineage presentation and claim boundaries match h9c.1"},
        {"invariant": "frozen_audit_procedure", "status": "passed", "checked_rows": str(len(procedure)), "detail": f"byte-identical to H8C; pipeline={owners['pipeline']} treatment_adapter={owners['treatment_adapter']}"},
        {"invariant": "manifested_inputs", "status": "passed", "checked_rows": "4", "detail": "H6 H6C H8C and H9A outputs pass checksum and row-count checks"},
        {"invariant": "same_request_set", "status": "passed", "checked_rows": str(len(audit_rows)), "detail": "B0 B1 B2 and B3 each audit the same 38 H6 observation IDs"},
        {"invariant": "inherited_rows_unchanged", "status": "passed", "checked_rows": str(len(inherited_audit)), "detail": "114 checksummed H8C audit rows are copied without recomputing their results"},
        {"invariant": "independent_b3_addressability", "status": "passed", "checked_rows": str(len(b3_audit)), "detail": "B3 reported outcomes agree with store and serving-state recomputation"},
        {"invariant": "exact_b3_reads", "status": "passed", "checked_rows": str(b3_addressable), "detail": "every B3 read matches identity decimal value and published lexeme"},
        {"invariant": "independent_impact_audit", "status": "passed", "checked_rows": str(len(impact_rows)), "detail": "dirty cells re-derived from the H8C graph equal H9A impact rows and arrival counts"},
        {"invariant": "last_dirty_arrival", "status": "passed", "checked_rows": str(len(current)), "detail": "each serving row was last recomputed at the last arrival that touched its cell"},
        {"invariant": "base_h8c_graph_immutable", "status": "passed", "checked_rows": str(graph_metrics["base_nodes"] + graph_metrics["base_edges"]), "detail": "294 H8C nodes and 810 edges retain their exact identities and fields"},
        {"invariant": "four_treatment_closure", "status": "passed", "checked_rows": str(len(closure_rows)), "detail": f"every request reaches its metric the four-treatment table and figure input; completeness={completeness:.4f}"},
        {"invariant": "figure_claim_boundary", "status": "passed", "checked_rows": str(len(figure_rows)), "detail": "figure data are ready but no rendered manuscript figure is claimed"},
        {"invariant": "measurement_boundary", "status": "passed", "checked_rows": "0", "detail": "no runtime byte or injected-workload result is claimed"},
    ]
    summary = [
        {"metric": "treatments_audited", "value": str(len(TREATMENTS)), "unit": "treatments", "interpretation": "B0 B1 B2 inherited from H8C plus B3"},
        {"metric": "total_audit_requests", "value": str(len(audit_rows)), "unit": "requests", "interpretation": "four treatments times 38 observations"},
        {"metric": "addressable_requests", "value": str(addressable), "unit": "requests", "interpretation": "B0=14 B1=38 B2=14 B3=38"},
        {"metric": "unavailable_requests", "value": str(unavailable), "unit": "requests", "interpretation": "B0=24 B1=0 B2=24 B3=0"},
        {"metric": "b3_vintage_key_successes", "value": str(sum(row["access_class"] == "vintage_key" for row in b3_audit)), "unit": "requests", "interpretation": "historical B3 reads served by the vintage key"},
        {"metric": "impact_rows_audited", "value": str(len(impact_rows)), "unit": "observations", "interpretation": "arriving observations traced to their dirty cell"},
        {"metric": "impact_mismatches", "value": str(impact_mismatches), "unit": "observations", "interpretation": "must remain zero"},
        {"metric": "closed_lineage_paths", "value": str(len(closure_rows)), "unit": "paths", "interpretation": "source through treatment and presentation evidence"},
        {"metric": "closure_completeness", "value": f"{completeness:.4f}", "unit": "ratio", "interpretation": "all four treatments"},
        {"metric": "closed_graph_nodes", "value": str(graph_metrics["closed_nodes"]), "unit": "nodes", "interpretation": f"H8C graph plus {sum(new_nodes.values())} B3 and presentation nodes"},
        {"metric": "closed_graph_edges", "value": str(graph_metrics["closed_edges"]), "unit": "edges", "interpretation": f"H8C graph plus {sum(new_edges.values())} exact identifier relationships"},
        {"metric": "figure_data_rows", "value": str(len(figure_rows)), "unit": "rows", "interpretation": "not a rendered manuscript figure"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (audit_output, AUDIT_COLUMNS, audit_rows),
        (impact_audit_output, IMPACT_AUDIT_COLUMNS, impact_rows),
        (metrics_output, METRIC_COLUMNS, metrics),
        (table_output, TABLE_COLUMNS, table_rows),
        (figure_output, FIGURE_COLUMNS, figure_rows),
        (nodes_output, NODE_COLUMNS, nodes),
        (edges_output, EDGE_COLUMNS, edges),
        (closure_output, CLOSURE_COLUMNS, closure_rows),
        (validation_output, VALIDATION_COLUMNS, validation),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H9",
        "track": "C",
        "contract_version": contract["contract_version"],
        "evidence_status": "validated",
        "scope": {
            "treatments": TREATMENTS,
            "new_treatment": "B3",
            "requests_per_treatment": 38,
        },
        "audit": {
            "total_requests": len(audit_rows),
            "addressable": addressable,
            "unavailable": unavailable,
            "b3_requests": len(b3_audit),
            "b3_addressable": b3_addressable,
            "row_failures": sum(row["audit_status"] != "passed" for row in audit_rows),
            "procedure_sha256": procedure_sha,
        },
        "impact": {"rows": len(impact_rows), "mismatches": impact_mismatches},
        "lineage": {
            **graph_metrics,
            "closure_completeness": f"{completeness:.4f}",
            "new_node_types": dict(sorted(new_nodes.items())),
            "new_relationships": dict(sorted(new_edges.items())),
        },
        "presentation": contract["presentation"],
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)}
            for path in (
                contract_path,
                procedure_path,
                h6_manifest_path,
                h6c_manifest_path,
                h8c_manifest_path,
                h9_manifest_path,
            )
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "base_nodes": graph_metrics["base_nodes"],
        "base_edges": graph_metrics["base_edges"],
        "closed_nodes": graph_metrics["closed_nodes"],
        "closed_edges": graph_metrics["closed_edges"],
        "audit_requests": len(audit_rows),
        "addressable": addressable,
        "unavailable": unavailable,
        "completeness": f"{completeness:.4f}",
        "treatments": len(TREATMENTS),
        "b3_requests": len(b3_audit),
        "b3_addressable": b3_addressable,
        "impact_rows": len(impact_rows),
        "impact_mismatches": impact_mismatches,
        "status": "validated",
    }
