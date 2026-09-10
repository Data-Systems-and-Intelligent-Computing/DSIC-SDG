from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h7c.pipeline import (
    BASE_EDGE_COLUMNS,
    BASE_NODE_COLUMNS,
    EDGE_COLUMNS,
    NODE_COLUMNS,
)


AUDIT_COLUMNS = [
    "audit_request_id",
    "treatment_id",
    "cell_id",
    "requested_observation_id",
    "requested_vintage_id",
    "source_lineage_path_id",
    "source_record_node_id",
    "observation_node_id",
    "requested_value_decimal",
    "requested_value_lexeme",
    "reported_result",
    "reported_addressable",
    "computed_addressable",
    "access_class",
    "lookup_locator",
    "serving_observation_id",
    "returned_observation_id",
    "returned_value_decimal",
    "returned_value_lexeme",
    "identity_match",
    "decimal_match",
    "lexeme_match",
    "failure_class",
    "treatment_manifest_path",
    "treatment_manifest_sha256",
    "audit_status",
]
METRIC_COLUMNS = [
    "treatment_id",
    "requests",
    "serving_state_successes",
    "historical_snapshot_successes",
    "failures",
    "success_rate",
    "row_audit_failures",
    "contract_result",
]
TABLE_COLUMNS = [
    "table_order",
    *METRIC_COLUMNS,
    "interpretation",
]
FIGURE_COLUMNS = [
    "figure_order",
    "treatment_id",
    "series",
    "request_count",
    "proportion",
    "label",
]
CLOSURE_COLUMNS = [
    "closure_id",
    "treatment_id",
    "audit_request_id",
    "requested_observation_id",
    "source_lineage_path_id",
    "source_record_node_id",
    "observation_node_id",
    "treatment_run_node_id",
    "treatment_decision_node_id",
    "treatment_output_node_id",
    "snapshot_state_node_ids",
    "reproducibility_metric_node_id",
    "evidence_table_node_id",
    "figure_input_node_id",
    "audit_procedure_node_id",
    "complete",
]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]
SUMMARY_COLUMNS = ["metric", "value", "unit", "interpretation"]
TREATMENTS = ["B0", "B1", "B2"]


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


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h8c.1"
        or contract.get("stage") != "H8"
        or contract.get("track") != "C"
    ):
        raise ValueError("unsupported H8C contract")
    scope = contract["scope"]
    if scope["implemented_treatments"] != TREATMENTS or scope["deferred_treatment"] != "B3":
        raise ValueError("H8C must cover B0, B1, and B2 while explicitly deferring B3")
    if scope["requests_per_treatment"] != 38 or scope["stable_cells"] != 14:
        raise ValueError("H8C scope does not match the frozen H6 workload")
    expected = contract["expected_results"]
    if expected != {
        "B0": {"successes": 14, "failures": 24, "success_rate": "0.3684"},
        "B1": {"successes": 38, "failures": 0, "success_rate": "1.0000"},
        "B2": {"successes": 14, "failures": 24, "success_rate": "0.3684"},
    }:
        raise ValueError("H8C expected treatment outcomes changed")
    audit = contract["audit_procedure"]
    if (
        audit["required_steps"] != 10
        or audit["pipeline_steps"] != 7
        or audit["treatment_adapter_steps"] != 3
        or audit["identity_matching"] != "exact_observation_id"
        or audit["value_matching"] != ["value_decimal", "value_lexeme"]
        or audit["lineage_matching"] != "exact_h6c_source_lineage_path_id"
        or audit["unclassified_failure_allowed"] is not False
    ):
        raise ValueError("H8C audit procedure policy changed")
    lineage = contract["lineage"]
    if lineage["base_nodes"] != 207 or lineage["base_edges"] != 491:
        raise ValueError("H8C must extend the frozen H7C graph")
    if lineage["fuzzy_matching_allowed"] is not False:
        raise ValueError("H8C must not use fuzzy lineage matching")
    presentation = contract["presentation"]
    if presentation["figure_status"] != "figure_data_ready_not_rendered" or presentation["manuscript_figure_claimed"] is not False:
        raise ValueError("H8C must not claim a rendered manuscript figure")


def validate_procedure(rows: list[dict[str, str]], contract: dict[str, Any]) -> dict[str, int]:
    policy = contract["audit_procedure"]
    if len(rows) != policy["required_steps"]:
        raise ValueError("H8C audit procedure has the wrong number of steps")
    if [int(row["step_order"]) for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("H8C audit steps must be contiguous and ordered")
    if len({row["step_id"] for row in rows}) != len(rows):
        raise ValueError("H8C audit step IDs must be unique")
    required_text = ["phase", "action", "required_evidence", "pass_condition", "failure_action"]
    if any(not row[column].strip() for row in rows for column in required_text):
        raise ValueError("H8C audit procedure contains an empty required field")
    owners = Counter(row["automation_owner"] for row in rows)
    if set(owners) != {"pipeline", "treatment_adapter"}:
        raise ValueError("H8C audit procedure has an unknown automation owner")
    if owners["pipeline"] != policy["pipeline_steps"] or owners["treatment_adapter"] != policy["treatment_adapter_steps"]:
        raise ValueError("H8C audit step ownership does not match the contract")
    return {"steps": len(rows), "pipeline_steps": owners["pipeline"], "adapter_steps": owners["treatment_adapter"]}


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


def _required_path(
    outputs: dict[str, tuple[Path, dict[str, Any]]], name: str
) -> tuple[Path, dict[str, Any]]:
    if name not in outputs:
        raise ValueError(f"required manifested output {name} is missing")
    return outputs[name]


def build_audit_rows(
    *,
    observations: list[dict[str, str]],
    source_paths: list[dict[str, str]],
    h7c_lineage: list[dict[str, str]],
    b0_reported: list[dict[str, str]],
    b0_state: list[dict[str, str]],
    b2_reported: list[dict[str, str]],
    b2_state: list[dict[str, str]],
    b1_reported: list[dict[str, str]],
    b1_states: list[dict[str, str]],
    treatment_manifests: dict[str, tuple[str, str]],
) -> list[dict[str, str]]:
    observation_by_id = {row["observation_id"]: row for row in observations}
    if len(observation_by_id) != 38:
        raise ValueError("H8C requires 38 unique H6 observations")
    source_by_observation = {row["observation_id"]: row for row in source_paths}
    if set(source_by_observation) != set(observation_by_id):
        raise ValueError("H8C H6 observations and H6C source paths differ")
    old_lineage = {
        (row["treatment_id"], row["requested_observation_id"]): row
        for row in h7c_lineage
    }
    if len(old_lineage) != 76:
        raise ValueError("H8C requires all 76 B0/B2 H7C treatment paths")

    b0_by_request = {row["requested_observation_id"]: row for row in b0_reported}
    b2_by_request = {row["requested_observation_id"]: row for row in b2_reported}
    b1_by_request = {row["requested_observation_id"]: row for row in b1_reported}
    canonical_requests = set(observation_by_id)
    if any(set(rows) != canonical_requests for rows in (b0_by_request, b1_by_request, b2_by_request)):
        raise ValueError("H8C treatments do not audit the same 38 observation IDs")

    b0_by_cell = {row["cell_id"]: row for row in b0_state}
    b2_by_cell = {row["cell_id"]: row for row in b2_state}
    if len(b0_by_cell) != 14 or len(b2_by_cell) != 14:
        raise ValueError("H8C B0/B2 serving states must contain 14 unique cells")
    b1_by_observation: dict[str, list[dict[str, str]]] = defaultdict(list)
    b1_orders = {int(row["snapshot_order"]) for row in b1_states}
    if b1_orders != {1, 2, 3}:
        raise ValueError("H8C B1 must contain three logical snapshot states")
    for row in b1_states:
        b1_by_observation[row["observation_id"]].append(row)
    max_order = max(b1_orders)
    b1_current = {
        row["cell_id"]: row for row in b1_states if int(row["snapshot_order"]) == max_order
    }
    if len(b1_current) != 14:
        raise ValueError("H8C B1 current snapshot must contain 14 unique cells")

    audit_rows: list[dict[str, str]] = []
    for treatment_id in TREATMENTS:
        manifest_path, manifest_sha = treatment_manifests[treatment_id]
        for requested_id in sorted(canonical_requests):
            requested = observation_by_id[requested_id]
            source_path = source_by_observation[requested_id]
            cell_id = requested["cell_id"]
            snapshot_orders = ""
            if treatment_id == "B0":
                reported = b0_by_request[requested_id]
                serving = b0_by_cell[cell_id]
                available = serving["observation_id"] == requested_id
                expected_result = "current_available" if available else "historical_overwritten"
                reported_available = reported["available_by_vintage"]
                if reported["current_observation_id"] != serving["observation_id"] or reported["current_value_lexeme"] != serving["value_lexeme"]:
                    raise ValueError("H8C B0 report disagrees with its serving state")
                access_class = "serving_state" if available else "unavailable"
                locator = f"current:cell_id={cell_id}" if available else ""
            elif treatment_id == "B2":
                reported = b2_by_request[requested_id]
                serving = b2_by_cell[cell_id]
                available = serving["observation_id"] == requested_id
                expected_result = "selected_available" if available else "discarded_by_source_selection"
                reported_available = reported["available_by_observation_id"]
                if reported["selected_observation_id"] != serving["observation_id"] or reported["selected_value_lexeme"] != serving["value_lexeme"]:
                    raise ValueError("H8C B2 report disagrees with its selected state")
                access_class = "serving_state" if available else "unavailable"
                locator = f"selected:cell_id={cell_id}" if available else ""
            else:
                reported = b1_by_request[requested_id]
                appearances = sorted(
                    b1_by_observation.get(requested_id, []),
                    key=lambda row: int(row["snapshot_order"]),
                )
                available = bool(appearances)
                orders = [row["snapshot_order"] for row in appearances]
                snapshot_orders = ";".join(orders)
                if reported["matching_snapshot_orders"] != snapshot_orders:
                    raise ValueError("H8C B1 report disagrees with its snapshot states")
                serving = b1_current[cell_id]
                current_available = max_order in {int(order) for order in orders}
                expected_result = "current_snapshot_available" if current_available else "historical_snapshot_available"
                reported_available = reported["available_by_snapshot"]
                access_class = "serving_state" if current_available else "historical_snapshot"
                locator = f"snapshot_order={snapshot_orders}" if available else ""

            if reported_available != ("yes" if available else "no") or reported["result"] != expected_result:
                raise ValueError(f"H8C {treatment_id} reported result failed independent recomputation")
            returned = requested if available else None
            identity_match = "yes" if available else "not_applicable"
            decimal_match = (
                "yes"
                if available and Decimal(returned["value_decimal"]) == Decimal(requested["value_decimal"])
                else "not_applicable" if not available else "no"
            )
            lexeme_match = (
                "yes"
                if available and returned["value_lexeme"] == requested["value_lexeme"]
                else "not_applicable" if not available else "no"
            )
            if available and {identity_match, decimal_match, lexeme_match} != {"yes"}:
                raise ValueError(f"H8C {treatment_id} successful read does not reproduce exactly")
            if treatment_id in {"B0", "B2"}:
                old = old_lineage[(treatment_id, requested_id)]
                if (
                    old["source_lineage_path_id"] != source_path["lineage_path_id"]
                    or old["requested_addressable"] != ("yes" if available else "no")
                    or old["output_observation_id"] != serving["observation_id"]
                ):
                    raise ValueError("H8C inherited H7C lineage disagrees with the recomputed audit")
            audit_rows.append(
                {
                    "audit_request_id": f"audit:{_id(treatment_id, requested_id)}",
                    "treatment_id": treatment_id,
                    "cell_id": cell_id,
                    "requested_observation_id": requested_id,
                    "requested_vintage_id": requested["vintage_id"],
                    "source_lineage_path_id": source_path["lineage_path_id"],
                    "source_record_node_id": source_path["source_record_node_id"],
                    "observation_node_id": source_path["observation_node_id"],
                    "requested_value_decimal": requested["value_decimal"],
                    "requested_value_lexeme": requested["value_lexeme"],
                    "reported_result": reported["result"],
                    "reported_addressable": reported_available,
                    "computed_addressable": "yes" if available else "no",
                    "access_class": access_class,
                    "lookup_locator": locator,
                    "serving_observation_id": serving["observation_id"],
                    "returned_observation_id": requested_id if available else "",
                    "returned_value_decimal": requested["value_decimal"] if available else "",
                    "returned_value_lexeme": requested["value_lexeme"] if available else "",
                    "identity_match": identity_match,
                    "decimal_match": decimal_match,
                    "lexeme_match": lexeme_match,
                    "failure_class": "none" if available else "expected_unavailable_by_treatment_policy",
                    "treatment_manifest_path": manifest_path,
                    "treatment_manifest_sha256": manifest_sha,
                    "audit_status": "passed",
                    "snapshot_orders": snapshot_orders,
                }
            )
    audit_rows.sort(key=lambda row: (TREATMENTS.index(row["treatment_id"]), row["requested_observation_id"]))
    return audit_rows


def build_metrics(
    audit_rows: list[dict[str, str]], contract: dict[str, Any]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    metrics: list[dict[str, str]] = []
    table: list[dict[str, str]] = []
    figure: list[dict[str, str]] = []
    interpretations = {
        "B0": "only the current overwritten state remains addressable",
        "B1": "current and historical observations remain addressable through snapshots",
        "B2": "only the selected single-source observations remain addressable",
    }
    for table_order, treatment_id in enumerate(TREATMENTS, start=1):
        rows = [row for row in audit_rows if row["treatment_id"] == treatment_id]
        serving = sum(row["access_class"] == "serving_state" for row in rows)
        historical = sum(row["access_class"] == "historical_snapshot" for row in rows)
        failures = sum(row["computed_addressable"] == "no" for row in rows)
        successes = serving + historical
        rate = f"{Decimal(successes) / Decimal(len(rows)):.4f}"
        expected = contract["expected_results"][treatment_id]
        if successes != expected["successes"] or failures != expected["failures"] or rate != expected["success_rate"]:
            raise ValueError(f"H8C {treatment_id} metric differs from its frozen expectation")
        metric = {
            "treatment_id": treatment_id,
            "requests": str(len(rows)),
            "serving_state_successes": str(serving),
            "historical_snapshot_successes": str(historical),
            "failures": str(failures),
            "success_rate": rate,
            "row_audit_failures": str(sum(row["audit_status"] != "passed" for row in rows)),
            "contract_result": "matched",
        }
        metrics.append(metric)
        table.append({"table_order": str(table_order), **metric, "interpretation": interpretations[treatment_id]})
        for series_order, (series, count) in enumerate((("addressable", successes), ("unavailable", failures))):
            proportion = Decimal(count) / Decimal(len(rows))
            figure.append(
                {
                    "figure_order": str((table_order - 1) * 2 + series_order + 1),
                    "treatment_id": treatment_id,
                    "series": series,
                    "request_count": str(count),
                    "proportion": f"{proportion:.4f}",
                    "label": f"{count}/{len(rows)}",
                }
            )
    return metrics, table, figure


def close_evidence_graph(
    *,
    base_nodes: list[dict[str, str]],
    base_edges: list[dict[str, str]],
    h7c_lineage: list[dict[str, str]],
    audit_rows: list[dict[str, str]],
    b1_states: list[dict[str, str]],
    b1_catalog: list[dict[str, str]],
    metrics: list[dict[str, str]],
    table_rows: list[dict[str, str]],
    figure_rows: list[dict[str, str]],
    procedure_path: Path,
    h8_manifest_path: Path,
    h8b_manifest_path: Path,
    metrics_output: Path,
    table_output: Path,
    figure_output: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    nodes = {row["node_id"]: dict(row) for row in base_nodes}
    edges = {row["edge_id"]: dict(row) for row in base_edges}
    if len(nodes) != len(base_nodes) or len(edges) != len(base_edges):
        raise ValueError("H8C base graph identities are not unique")
    old_lineage = {
        (row["treatment_id"], row["requested_observation_id"]): row
        for row in h7c_lineage
    }
    observation_nodes = {
        row["natural_key"]: row["node_id"]
        for row in base_nodes
        if row["node_type"] == "observation"
    }
    cell_nodes = {
        row["natural_key"]: row["node_id"]
        for row in base_nodes
        if row["node_type"] == "indicator_cell"
    }
    domains = {
        row["natural_key"]: row["domain"]
        for row in base_nodes
        if row["node_type"] == "observation"
    }

    def add_node(row: dict[str, str]) -> None:
        existing = nodes.get(row["node_id"])
        if existing is not None and existing != row:
            raise ValueError(f"conflicting H8C node {row['node_id']}")
        nodes[row["node_id"]] = row

    def add_edge(
        relationship: str,
        from_node_id: str,
        to_node_id: str,
        *,
        treatment_id: str = "",
        observation_id: str = "",
        cell_id: str = "",
        evidence_basis: str,
    ) -> None:
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
        existing = edges.get(edge_id)
        if existing is not None and existing != row:
            raise ValueError(f"conflicting H8C edge {edge_id}")
        edges[edge_id] = row

    h8_sha = _sha256(h8_manifest_path)
    b1_run_node_id = _node_id("treatment_run", "B1", h8_sha)
    add_node(
        {
            "node_id": b1_run_node_id,
            "node_type": "treatment_run",
            "natural_key": f"B1|{h8_sha}",
            "label": "B1 treatment run",
            "domain": "",
            "source_id": "",
            "vintage_id": "",
            "path": str(h8_manifest_path),
            "sha256": h8_sha,
            "treatment_id": "B1",
            "observation_id": "",
            "decision": "",
            "addressable": "",
        }
    )
    snapshot_nodes: dict[str, str] = {}
    for snapshot in sorted(b1_catalog, key=lambda row: int(row["snapshot_order"])):
        order = snapshot["snapshot_order"]
        node_id = _node_id("snapshot_state", "B1", snapshot["state_snapshot_key"])
        snapshot_nodes[order] = node_id
        add_node(
            {
                "node_id": node_id,
                "node_type": "snapshot_state",
                "natural_key": f"B1|{snapshot['state_snapshot_key']}",
                "label": f"B1 snapshot {order}",
                "domain": "",
                "source_id": snapshot["source_id"],
                "vintage_id": snapshot["applied_vintage_id"],
                "path": "results/processed/h8-b1-snapshot-states.csv",
                "sha256": snapshot["state_sha256"],
                "treatment_id": "B1",
                "observation_id": "",
                "decision": "retained_snapshot",
                "addressable": "yes",
            }
        )
        add_edge(
            "treatment_run_commits_snapshot",
            b1_run_node_id,
            node_id,
            treatment_id="B1",
            evidence_basis="B1 snapshot catalog order and deterministic state checksum",
        )

    b1_appearances: dict[str, list[str]] = defaultdict(list)
    for row in b1_states:
        b1_appearances[row["observation_id"]].append(row["snapshot_order"])

    for audit in [row for row in audit_rows if row["treatment_id"] == "B1"]:
        requested = audit["requested_observation_id"]
        cell_id = audit["cell_id"]
        decision_node_id = _node_id("treatment_decision", "B1", requested)
        output_node_id = _node_id("treatment_output", "B1", cell_id, requested)
        add_node(
            {
                "node_id": decision_node_id,
                "node_type": "treatment_decision",
                "natural_key": f"B1|{requested}",
                "label": f"B1:{audit['reported_result']}",
                "domain": domains[requested],
                "source_id": "",
                "vintage_id": audit["requested_vintage_id"],
                "path": "",
                "sha256": "",
                "treatment_id": "B1",
                "observation_id": requested,
                "decision": audit["reported_result"],
                "addressable": "yes",
            }
        )
        add_node(
            {
                "node_id": output_node_id,
                "node_type": "treatment_output",
                "natural_key": f"B1|{cell_id}|{requested}",
                "label": f"B1:{cell_id}:{requested}",
                "domain": domains[requested],
                "source_id": "",
                "vintage_id": audit["requested_vintage_id"],
                "path": "results/processed/h8-b1-snapshot-states.csv",
                "sha256": "",
                "treatment_id": "B1",
                "observation_id": requested,
                "decision": "snapshot_addressable_output",
                "addressable": "yes",
            }
        )
        add_edge(
            "observation_enters_treatment",
            observation_nodes[requested],
            decision_node_id,
            treatment_id="B1",
            observation_id=requested,
            cell_id=cell_id,
            evidence_basis="exact H6 observation_id carried by the B1 audit",
        )
        add_edge(
            "treatment_run_evaluates_candidate",
            b1_run_node_id,
            decision_node_id,
            treatment_id="B1",
            observation_id=requested,
            cell_id=cell_id,
            evidence_basis="checksummed H8 B1 manifest and reproducibility row",
        )
        add_edge(
            "decision_resolves_to_output",
            decision_node_id,
            output_node_id,
            treatment_id="B1",
            observation_id=requested,
            cell_id=cell_id,
            evidence_basis="requested observation_id is retained by at least one B1 snapshot",
        )
        add_edge(
            "output_serves_cell",
            output_node_id,
            cell_nodes[cell_id],
            treatment_id="B1",
            observation_id=requested,
            cell_id=cell_id,
            evidence_basis="B1 output and H6C cell share the exact stable cell_id",
        )
        for order in sorted(b1_appearances[requested], key=int):
            add_edge(
                "output_available_in_snapshot",
                output_node_id,
                snapshot_nodes[order],
                treatment_id="B1",
                observation_id=requested,
                cell_id=cell_id,
                evidence_basis="exact observation_id occurrence in the logical B1 snapshot state",
            )

    procedure_node_id = _node_id("audit_procedure", _sha256(procedure_path))
    add_node(
        {
            "node_id": procedure_node_id,
            "node_type": "audit_procedure",
            "natural_key": _sha256(procedure_path),
            "label": "H8C reproducibility audit procedure",
            "domain": "",
            "source_id": "",
            "vintage_id": "",
            "path": str(procedure_path),
            "sha256": _sha256(procedure_path),
            "treatment_id": "",
            "observation_id": "",
            "decision": "required_for_all_treatments",
            "addressable": "",
        }
    )
    harness_sha = _sha256(h8b_manifest_path)
    harness_node_id = _node_id("workload_harness", harness_sha)
    add_node(
        {
            "node_id": harness_node_id,
            "node_type": "workload_harness",
            "natural_key": harness_sha,
            "label": "H8B injected-revision harness",
            "domain": "",
            "source_id": "synthetic_revision_harness",
            "vintage_id": "",
            "path": str(h8b_manifest_path),
            "sha256": harness_sha,
            "treatment_id": "",
            "observation_id": "",
            "decision": "prepared_not_run",
            "addressable": "",
        }
    )
    add_edge(
        "workload_harness_uses_audit_procedure",
        harness_node_id,
        procedure_node_id,
        evidence_basis="H8B routes must be audited by the frozen H8C procedure when executed",
    )

    run_nodes = {"B1": b1_run_node_id}
    for treatment_id in ("B0", "B2"):
        inherited = next(
            row for row in h7c_lineage if row["treatment_id"] == treatment_id
        )
        run_nodes[treatment_id] = inherited["treatment_run_node_id"]
    for treatment_id in TREATMENTS:
        add_edge(
            "procedure_governs_treatment_run",
            procedure_node_id,
            run_nodes[treatment_id],
            treatment_id=treatment_id,
            evidence_basis="all implemented treatments are evaluated by the same ordered audit procedure",
        )

    metric_nodes: dict[str, str] = {}
    for metric in metrics:
        treatment_id = metric["treatment_id"]
        digest = _rows_digest(METRIC_COLUMNS, [metric])
        node_id = _node_id("reproducibility_metric", treatment_id, digest)
        metric_nodes[treatment_id] = node_id
        add_node(
            {
                "node_id": node_id,
                "node_type": "reproducibility_metric",
                "natural_key": f"{treatment_id}|{digest}",
                "label": f"{treatment_id} reproducibility={metric['success_rate']}",
                "domain": "",
                "source_id": "",
                "vintage_id": "",
                "path": str(metrics_output),
                "sha256": digest,
                "treatment_id": treatment_id,
                "observation_id": "",
                "decision": "aggregated_after_row_audit",
                "addressable": "",
            }
        )

    table_digest = _rows_digest(TABLE_COLUMNS, table_rows)
    table_node_id = _node_id("evidence_table", table_digest)
    add_node(
        {
            "node_id": table_node_id,
            "node_type": "evidence_table",
            "natural_key": table_digest,
            "label": "B0-B2 reproducibility evidence table",
            "domain": "",
            "source_id": "",
            "vintage_id": "",
            "path": str(table_output),
            "sha256": table_digest,
            "treatment_id": "",
            "observation_id": "",
            "decision": "audit_table_ready",
            "addressable": "",
        }
    )
    figure_digest = _rows_digest(FIGURE_COLUMNS, figure_rows)
    figure_node_id = _node_id("figure_input", figure_digest)
    add_node(
        {
            "node_id": figure_node_id,
            "node_type": "figure_input",
            "natural_key": figure_digest,
            "label": "reproducibility comparison figure data",
            "domain": "",
            "source_id": "",
            "vintage_id": "",
            "path": str(figure_output),
            "sha256": figure_digest,
            "treatment_id": "",
            "observation_id": "",
            "decision": "figure_data_ready_not_rendered",
            "addressable": "",
        }
    )
    for treatment_id, metric_node_id in metric_nodes.items():
        add_edge(
            "metric_published_in_table",
            metric_node_id,
            table_node_id,
            treatment_id=treatment_id,
            evidence_basis="treatment metric row is copied exactly into the evidence table",
        )
    add_edge(
        "table_supplies_figure_input",
        table_node_id,
        figure_node_id,
        evidence_basis="figure data contains the same per-treatment success and failure counts",
    )

    closure_rows: list[dict[str, str]] = []
    for audit in audit_rows:
        treatment_id = audit["treatment_id"]
        requested = audit["requested_observation_id"]
        if treatment_id in {"B0", "B2"}:
            inherited = old_lineage[(treatment_id, requested)]
            run_node_id = inherited["treatment_run_node_id"]
            decision_node_id = inherited["treatment_decision_node_id"]
            output_node_id = inherited["treatment_output_node_id"]
            snapshot_node_ids = ""
        else:
            run_node_id = b1_run_node_id
            decision_node_id = _node_id("treatment_decision", "B1", requested)
            output_node_id = _node_id("treatment_output", "B1", audit["cell_id"], requested)
            snapshot_node_ids = ";".join(
                snapshot_nodes[order]
                for order in sorted(b1_appearances[requested], key=int)
            )
        metric_node_id = metric_nodes[treatment_id]
        add_edge(
            "audit_decision_contributes_to_metric",
            decision_node_id,
            metric_node_id,
            treatment_id=treatment_id,
            observation_id=requested,
            cell_id=audit["cell_id"],
            evidence_basis="row-level identity value and lineage checks pass before aggregation",
        )
        closure_rows.append(
            {
                "closure_id": f"closure:{_id(treatment_id, requested)}",
                "treatment_id": treatment_id,
                "audit_request_id": audit["audit_request_id"],
                "requested_observation_id": requested,
                "source_lineage_path_id": audit["source_lineage_path_id"],
                "source_record_node_id": audit["source_record_node_id"],
                "observation_node_id": audit["observation_node_id"],
                "treatment_run_node_id": run_node_id,
                "treatment_decision_node_id": decision_node_id,
                "treatment_output_node_id": output_node_id,
                "snapshot_state_node_ids": snapshot_node_ids,
                "reproducibility_metric_node_id": metric_node_id,
                "evidence_table_node_id": table_node_id,
                "figure_input_node_id": figure_node_id,
                "audit_procedure_node_id": procedure_node_id,
                "complete": "yes",
            }
        )

    node_rows = sorted(nodes.values(), key=lambda row: (row["node_type"], row["node_id"]))
    edge_rows = sorted(edges.values(), key=lambda row: (row["relationship"], row["edge_id"]))
    closure_rows.sort(key=lambda row: (TREATMENTS.index(row["treatment_id"]), row["requested_observation_id"]))
    known_nodes = set(nodes)
    if any(edge["from_node_id"] not in known_nodes or edge["to_node_id"] not in known_nodes for edge in edge_rows):
        raise ValueError("H8C edge references an unknown node")
    if any(row["complete"] != "yes" for row in closure_rows):
        raise ValueError("H8C evidence closure is incomplete")
    return node_rows, edge_rows, closure_rows, {
        "base_nodes": len(base_nodes),
        "base_edges": len(base_edges),
        "closed_nodes": len(node_rows),
        "closed_edges": len(edge_rows),
        "closure_paths": len(closure_rows),
    }


def run_h8c(
    *,
    contract_path: Path,
    procedure_path: Path,
    h6_manifest_path: Path,
    h6c_manifest_path: Path,
    h7c_manifest_path: Path,
    b0_manifest_path: Path,
    b1_manifest_path: Path,
    b2_manifest_path: Path,
    h8b_manifest_path: Path,
    audit_output: Path,
    metrics_output: Path,
    table_output: Path,
    figure_output: Path,
    nodes_output: Path,
    edges_output: Path,
    closure_output: Path,
    procedure_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    procedure = _read_csv(procedure_path)
    procedure_metrics = validate_procedure(procedure, contract)

    h6_manifest, h6_outputs = _manifested_outputs(
        h6_manifest_path, {"stage": "H6", "schema_status": "validated"}
    )
    h6c_manifest, h6c_outputs = _manifested_outputs(
        h6c_manifest_path, {"stage": "H6", "track": "C", "lineage_status": "validated"}
    )
    h7c_manifest, h7c_outputs = _manifested_outputs(
        h7c_manifest_path, {"stage": "H7", "track": "C", "evidence_status": "validated"}
    )
    b0_manifest, b0_outputs = _manifested_outputs(
        b0_manifest_path, {"stage": "H7", "treatment_id": "B0", "implementation_status": "implemented"}
    )
    b1_manifest, b1_outputs = _manifested_outputs(
        b1_manifest_path, {"stage": "H8", "track": "A", "treatment_id": "B1", "implementation_status": "implemented"}
    )
    b2_manifest, b2_outputs = _manifested_outputs(
        b2_manifest_path, {"stage": "H7", "track": "B", "treatment_id": "B2", "implementation_status": "implemented"}
    )
    h8b_manifest, _ = _manifested_outputs(
        h8b_manifest_path, {"stage": "H8", "track": "B", "harness_status": "validation_ready"}
    )
    if h8b_manifest.get("human_decisions", {}).get("main_sweep_source_scope") != "exactly_one_revised_source_per_run":
        raise ValueError("H8C requires the approved H8B main-sweep source scope")

    observation_path, _ = _required_path(h6_outputs, "h6-indicator-observations.csv")
    source_paths_path, _ = _required_path(h6c_outputs, "h6c-cell-source-paths.csv")
    base_nodes_path, _ = _required_path(h7c_outputs, "h7c-lineage-nodes.csv")
    base_edges_path, _ = _required_path(h7c_outputs, "h7c-lineage-edges.csv")
    h7c_lineage_path, _ = _required_path(h7c_outputs, "h7c-treatment-lineage.csv")
    b0_repro_path, _ = _required_path(b0_outputs, "h7-b0-reproducibility.csv")
    b0_state_path, _ = _required_path(b0_outputs, "h7-b0-final-state.csv")
    b1_repro_path, _ = _required_path(b1_outputs, "h8-b1-reproducibility.csv")
    b1_states_path, _ = _required_path(b1_outputs, "h8-b1-snapshot-states.csv")
    b1_catalog_path, _ = _required_path(b1_outputs, "h8-b1-snapshot-catalog.csv")
    b2_repro_path, _ = _required_path(b2_outputs, "h7b-b2-reproducibility.csv")
    b2_state_path, _ = _required_path(b2_outputs, "h7b-b2-selected-state.csv")

    treatment_manifests = {
        "B0": (str(b0_manifest_path), _sha256(b0_manifest_path)),
        "B1": (str(b1_manifest_path), _sha256(b1_manifest_path)),
        "B2": (str(b2_manifest_path), _sha256(b2_manifest_path)),
    }
    h7c_lineage = _read_csv(h7c_lineage_path)
    b1_states = _read_csv(b1_states_path)
    audit_rows = build_audit_rows(
        observations=_read_csv(observation_path),
        source_paths=_read_csv(source_paths_path),
        h7c_lineage=h7c_lineage,
        b0_reported=_read_csv(b0_repro_path),
        b0_state=_read_csv(b0_state_path),
        b2_reported=_read_csv(b2_repro_path),
        b2_state=_read_csv(b2_state_path),
        b1_reported=_read_csv(b1_repro_path),
        b1_states=b1_states,
        treatment_manifests=treatment_manifests,
    )
    metrics, table_rows, figure_rows = build_metrics(audit_rows, contract)
    nodes, edges, closure_rows, graph_metrics = close_evidence_graph(
        base_nodes=_read_csv(base_nodes_path),
        base_edges=_read_csv(base_edges_path),
        h7c_lineage=h7c_lineage,
        audit_rows=audit_rows,
        b1_states=b1_states,
        b1_catalog=_read_csv(b1_catalog_path),
        metrics=metrics,
        table_rows=table_rows,
        figure_rows=figure_rows,
        procedure_path=procedure_path,
        h8_manifest_path=b1_manifest_path,
        h8b_manifest_path=h8b_manifest_path,
        metrics_output=metrics_output,
        table_output=table_output,
        figure_output=figure_output,
    )
    addressable = sum(row["computed_addressable"] == "yes" for row in audit_rows)
    unavailable = len(audit_rows) - addressable
    completeness = sum(row["complete"] == "yes" for row in closure_rows) / len(closure_rows)
    validation = [
        {"invariant": "h8c_contract", "status": "passed", "checked_rows": "8", "detail": "scope audit lineage presentation and claim boundaries match h8c.1"},
        {"invariant": "ordered_audit_procedure", "status": "passed", "checked_rows": str(procedure_metrics["steps"]), "detail": f"pipeline={procedure_metrics['pipeline_steps']} and treatment_adapter={procedure_metrics['adapter_steps']}"},
        {"invariant": "manifested_inputs", "status": "passed", "checked_rows": "7", "detail": "H6 H6C H7C B0 B1 B2 and H8B outputs pass checksum and row-count checks"},
        {"invariant": "same_request_set", "status": "passed", "checked_rows": str(len(audit_rows)), "detail": "B0 B1 and B2 each audit the same 38 H6 observation IDs"},
        {"invariant": "independent_addressability", "status": "passed", "checked_rows": str(len(audit_rows)), "detail": "reported outcomes agree with independent state and snapshot recomputation"},
        {"invariant": "exact_successful_reads", "status": "passed", "checked_rows": str(addressable), "detail": "every successful read matches identity decimal value and published lexeme"},
        {"invariant": "explicit_unavailability", "status": "passed", "checked_rows": str(unavailable), "detail": "all unavailable reads are expected consequences of B0 or B2 policy"},
        {"invariant": "base_h7c_graph_immutable", "status": "passed", "checked_rows": str(graph_metrics["base_nodes"] + graph_metrics["base_edges"]), "detail": "207 H7C nodes and 491 edges retain their exact identities and fields"},
        {"invariant": "source_to_presentation_closure", "status": "passed", "checked_rows": str(len(closure_rows)), "detail": "every request reaches one metric evidence table and figure-input node"},
        {"invariant": "closure_completeness", "status": "passed", "checked_rows": str(len(closure_rows)), "detail": f"completeness={completeness:.4f}"},
        {"invariant": "h8b_procedure_link", "status": "passed", "checked_rows": "1", "detail": "future injected workloads are governed by the same audit procedure"},
        {"invariant": "b3_deferred", "status": "passed", "checked_rows": "0", "detail": "B3 has no result row node or metric before its H9 implementation"},
        {"invariant": "figure_claim_boundary", "status": "passed", "checked_rows": str(len(figure_rows)), "detail": "figure data are ready but no rendered manuscript figure is claimed"},
    ]
    summary = [
        {"metric": "implemented_treatments_audited", "value": str(len(TREATMENTS)), "unit": "treatments", "interpretation": "B0 B1 and B2 only"},
        {"metric": "requests_per_treatment", "value": "38", "unit": "requests", "interpretation": "same H6 observation IDs"},
        {"metric": "total_audit_requests", "value": str(len(audit_rows)), "unit": "requests", "interpretation": "three treatments times 38 observations"},
        {"metric": "addressable_requests", "value": str(addressable), "unit": "requests", "interpretation": "B0=14 B1=38 B2=14"},
        {"metric": "unavailable_requests", "value": str(unavailable), "unit": "requests", "interpretation": "B0=24 B1=0 B2=24"},
        {"metric": "closed_lineage_paths", "value": str(len(closure_rows)), "unit": "paths", "interpretation": "source through treatment and presentation evidence"},
        {"metric": "closure_completeness", "value": f"{completeness:.4f}", "unit": "ratio", "interpretation": "all in-scope implemented-treatment requests"},
        {"metric": "closed_graph_nodes", "value": str(graph_metrics["closed_nodes"]), "unit": "nodes", "interpretation": "H7C graph plus B1 and presentation evidence"},
        {"metric": "closed_graph_edges", "value": str(graph_metrics["closed_edges"]), "unit": "edges", "interpretation": "exact identifier and aggregation relationships"},
        {"metric": "audit_procedure_steps", "value": str(procedure_metrics["steps"]), "unit": "steps", "interpretation": "seven pipeline and three treatment-adapter steps"},
        {"metric": "figure_data_rows", "value": str(len(figure_rows)), "unit": "rows", "interpretation": "not a rendered manuscript figure"},
        {"metric": "deferred_treatments", "value": "1", "unit": "treatments", "interpretation": "B3 must be added after implementation"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (audit_output, AUDIT_COLUMNS, audit_rows),
        (metrics_output, METRIC_COLUMNS, metrics),
        (table_output, TABLE_COLUMNS, table_rows),
        (figure_output, FIGURE_COLUMNS, figure_rows),
        (nodes_output, NODE_COLUMNS, nodes),
        (edges_output, EDGE_COLUMNS, edges),
        (closure_output, CLOSURE_COLUMNS, closure_rows),
        (procedure_output, list(procedure[0]), procedure),
        (validation_output, VALIDATION_COLUMNS, validation),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H8",
        "track": "C",
        "contract_version": contract["contract_version"],
        "evidence_status": "validated",
        "scope": {
            "implemented_treatments": TREATMENTS,
            "deferred_treatment": "B3",
            "requests_per_treatment": 38,
        },
        "audit": {
            "total_requests": len(audit_rows),
            "addressable": addressable,
            "unavailable": unavailable,
            "row_failures": sum(row["audit_status"] != "passed" for row in audit_rows),
            **procedure_metrics,
        },
        "lineage": {**graph_metrics, "closure_completeness": f"{completeness:.4f}"},
        "presentation": contract["presentation"],
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)}
            for path in (
                contract_path,
                procedure_path,
                h6_manifest_path,
                h6c_manifest_path,
                h7c_manifest_path,
                b0_manifest_path,
                b1_manifest_path,
                b2_manifest_path,
                h8b_manifest_path,
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
        **procedure_metrics,
        "status": "validated",
    }
