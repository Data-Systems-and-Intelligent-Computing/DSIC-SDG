from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h6.pipeline import VINTAGE_COLUMNS
from kkciv_vintage.h7.pipeline import simulate_overwrite
from kkciv_vintage.h8.pipeline import simulate_full_snapshots
from kkciv_vintage.h9.pipeline import IMPACT_RELATIONSHIP, simulate_vintage_aware


TREATMENTS = ["B0", "B1", "B2", "B3"]
SYNTHETIC_SOURCE = "synthetic_revision_harness"
SYNTHETIC_EVIDENCE = "synthetic_not_official"
REQUIRED_DECISIONS = {
    "h9_b3_history_as_rows": ("b3_history", "store_history_as_append_only_rows_and_allow_snapshot_expiry"),
    "h9_b3_resolution_key": ("b3_resolution", "vintage_date_then_retrieved_at_then_vintage_id"),
    "h9_b3_materialized_serving": ("b3_serving", "materialize_serving_table"),
    "h9_synthetic_vintage_ordering": ("synthetic_vintage", "one_day_after_latest_official_vintage"),
}
SYNTHETIC_VINTAGE_COLUMNS = ["scenario_order", "scenario_id", *VINTAGE_COLUMNS]
ROUTE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "treatment_id",
    "workload_sha256",
    "payload_verified",
    "input_rows",
    "revised_source_mix",
    "single_revised_source",
    "synthetic_vintage_id",
    "synthetic_vintage_date",
    "cells_evaluated",
    "rows_written_logical",
    "serving_changed_cells",
    "serving_value_changed_cells",
    "synthetic_observations_served",
    "latest_vintage_cells",
    "requests",
    "addressable_requests",
    "unavailable_requests",
    "revised_base_recalled",
    "incremental_equals_full",
    "execution_status",
    "timing",
    "storage",
]
STATE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "treatment_id",
    "cell_id",
    "observation_id",
    "vintage_id",
    "value_lexeme",
    "synthetic",
    "changed_vs_baseline",
]
RECALL_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "treatment_id",
    "requested_observation_id",
    "request_kind",
    "cell_id",
    "addressable",
]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]
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


def _manifest_outputs(
    manifest_path: Path, requirements: dict[str, str]
) -> dict[str, tuple[Path, dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in requirements.items()):
        raise ValueError(f"H9B requires a valid {manifest_path} input")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested output {path}")
        if "rows" in item and len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested output {path}")
        outputs[path.name] = (path, item)
    return outputs


def _required(outputs: dict[str, tuple[Path, dict[str, Any]]], name: str) -> Path:
    if name not in outputs:
        raise ValueError(f"required manifested output {name} is missing")
    return outputs[name][0]


def _payload_hash(rows: list[dict[str, str]]) -> str:
    # Same canonical payload digest as the H8B route builder; a drift fails the route check.
    digest = hashlib.sha256()
    digest.update(b"cell_id\x1fafter_value_decimal\x1fsynthetic_observation_id\n")
    for row in rows:
        digest.update(
            (
                f"{row['cell_id']}\x1f{row['after_value_decimal']}\x1f"
                f"{row['synthetic_observation_id']}\n"
            ).encode("utf-8")
        )
    return digest.hexdigest()


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h9b.1"
        or contract.get("stage") != "H9"
        or contract.get("track") != "B"
    ):
        raise ValueError("unsupported H9B contract")
    source = contract["input"]
    if (
        source["harness_contract_version"] != "h8b.2"
        or source["profile_status"] != "validation_only"
        or source["treatments"] != TREATMENTS
    ):
        raise ValueError("H9B must execute the frozen H8B validation profile on all four treatments")
    if contract["human_decisions"]["decision_ids"] != list(REQUIRED_DECISIONS):
        raise ValueError("H9B human decisions do not match the approved registry")
    synthetic = contract["synthetic_vintage"]
    if (
        synthetic["vintage_date_rule"] != "latest_official_vintage_date_plus_one_day"
        or synthetic["retrieved_at_time"] != "00:00:00+00:00"
        or synthetic["tie_break"] != "vintage_id"
        or synthetic["source_id"] != SYNTHETIC_SOURCE
    ):
        raise ValueError("H9B synthetic vintage ordering does not match the approved rule")
    provenance = contract["synthetic_provenance"]
    if (
        provenance["producer"] != SYNTHETIC_SOURCE
        or provenance["evidence_level"] != SYNTHETIC_EVIDENCE
        or provenance["must_not_masquerade_as_bps"] is not True
    ):
        raise ValueError("H9B synthetic rows must never masquerade as BPS")
    execution = contract["execution"]
    if (
        execution["mode"] != "logical"
        or execution["route_status"] != "executed_logical"
        or execution["timing"] != "not_measured"
        or execution["storage"] != "not_measured"
    ):
        raise ValueError("H9B must not claim physical execution, timing, or storage")


def validate_human_decisions(rows: list[dict[str, str]]) -> None:
    by_id = {row["decision_id"]: row for row in rows}
    if len(rows) != len(REQUIRED_DECISIONS) or set(by_id) != set(REQUIRED_DECISIONS):
        raise ValueError("H9B requires exactly the four H9 human decisions")
    for decision_id, (scope, decision) in REQUIRED_DECISIONS.items():
        row = by_id[decision_id]
        if (
            row["decided_at"] != "2026-09-11"
            or row["decided_by"] != "human_reviewer"
            or row["status"] != "approved"
            or row["scope"] != scope
            or row["decision"] != decision
            or not row["rationale"]
        ):
            raise ValueError(f"H9 human decision {decision_id} is not approved as recorded")


def synthetic_vintage_row(
    official_vintages: list[dict[str, str]],
    scenario: dict[str, str],
    *,
    manifest_path: str,
    manifest_sha: str,
) -> dict[str, str]:
    latest = max(date.fromisoformat(row["vintage_date"]) for row in official_vintages)
    vintage_date = (latest + timedelta(days=1)).isoformat()
    return {
        "vintage_id": scenario["synthetic_vintage_id"],
        "source_id": SYNTHETIC_SOURCE,
        "source_channel": "synthetic",
        "vintage_date": vintage_date,
        "vintage_basis": "synthetic_injected_revision",
        "retrieved_at": f"{vintage_date}T00:00:00+00:00",
        "release_label": f"H8B {scenario['scenario_id']} synthetic revision (not BPS)",
        "source_manifest_path": manifest_path,
        "source_manifest_sha256": manifest_sha,
    }


def synthetic_observations(
    injections: list[dict[str, str]],
    base_by_id: dict[str, dict[str, str]],
    *,
    artifact_path: str,
    artifact_sha: str,
    run_id: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for injection in injections:
        base = base_by_id.get(injection["base_observation_id"])
        if base is None or base["cell_id"] != injection["cell_id"]:
            raise ValueError(f"injection {injection['synthetic_observation_id']} does not revise a known base cell")
        if injection["provenance_class"] != SYNTHETIC_EVIDENCE:
            raise ValueError("H9B accepts only rows labeled synthetic_not_official")
        rows.append(
            {
                "observation_id": injection["synthetic_observation_id"],
                "cell_id": injection["cell_id"],
                "vintage_id": injection["synthetic_vintage_id"],
                **{
                    column: injection[column]
                    for column in (
                        "domain",
                        "indicator_key",
                        "series_key",
                        "observed_period",
                        "period_granularity",
                        "geo_level",
                        "geo_code",
                        "geo_name",
                        "unit",
                        "published_decimal_places",
                    )
                },
                "value_decimal": injection["after_value_decimal"],
                "value_lexeme": injection["after_value_lexeme"],
                "producer": SYNTHETIC_SOURCE,
                "methodology_version": base["methodology_version"],
                "source_artifact_path": artifact_path,
                "source_artifact_sha256": artifact_sha,
                "source_record_id": f"scenario_id={injection['scenario_id']};selection_rank={injection['selection_rank']}",
                "ingestion_batch_id": f"h8b-{injection['synthetic_vintage_id']}",
                "transformation_run_id": run_id,
                "transformation_version": "h9b-adapter-v1",
                "trace_id": "",
                "cause_family": "synthetic_revision",
                "evidence_level": SYNTHETIC_EVIDENCE,
            }
        )
    return rows


def synthetic_lineage(
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    injections: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    observation_nodes = {row["natural_key"]: row for row in nodes if row["node_type"] == "observation"}
    cell_edge_by_node = {
        row["from_node_id"]: row for row in edges if row["relationship"] == IMPACT_RELATIONSHIP
    }
    extra_nodes: list[dict[str, str]] = []
    extra_edges: list[dict[str, str]] = []
    for injection in injections:
        base_node = observation_nodes.get(injection["base_observation_id"])
        if base_node is None or base_node["node_id"] not in cell_edge_by_node:
            raise ValueError(f"base observation {injection['base_observation_id']} has no H6C cell edge")
        base_edge = cell_edge_by_node[base_node["node_id"]]
        node_id = f"observation:{_id('H9B', injection['synthetic_observation_id'])}"
        extra_nodes.append(
            {
                **base_node,
                "node_id": node_id,
                "natural_key": injection["synthetic_observation_id"],
                "label": injection["synthetic_observation_id"],
                "source_id": SYNTHETIC_SOURCE,
                "vintage_id": injection["synthetic_vintage_id"],
            }
        )
        extra_edges.append(
            {
                **base_edge,
                "edge_id": f"edge:{_id('H9B', IMPACT_RELATIONSHIP, node_id)}",
                "from_node_id": node_id,
                "observation_id": injection["synthetic_observation_id"],
                "evidence_basis": f"synthetic revision inherits base edge {base_edge['edge_id']}",
            }
        )
    return [*nodes, *extra_nodes], [*edges, *extra_edges]


def select_single_source(
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    score_by_source: dict[str, Decimal],
    scoring_source_by_observation: dict[str, str],
) -> dict[str, dict[str, str]]:
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    by_cell: dict[str, list[dict[str, str]]] = {}
    for row in observations:
        by_cell.setdefault(row["cell_id"], []).append(row)
    selected: dict[str, dict[str, str]] = {}
    for cell_id, candidates in sorted(by_cell.items()):
        enriched = []
        for row in candidates:
            source_id = scoring_source_by_observation.get(
                row["observation_id"], vintage_by_id[row["vintage_id"]]["source_id"]
            )
            if source_id not in score_by_source:
                raise ValueError(f"B2 has no frozen score for source {source_id}")
            enriched.append(
                (row, source_id, vintage_by_id[row["vintage_id"]]["vintage_date"])
            )
        ranked = sorted(enriched, key=lambda item: (item[1], item[0]["observation_id"]))
        ranked.sort(key=lambda item: item[2], reverse=True)
        ranked.sort(key=lambda item: score_by_source[item[1]], reverse=True)
        selected[cell_id] = ranked[0][0]
    return selected


def run_treatments(
    *,
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    score_by_source: dict[str, Decimal],
    scoring_source_by_observation: dict[str, str],
) -> dict[str, dict[str, Any]]:
    _, b0_state, b0_reads, _ = simulate_overwrite(vintages, observations)
    b1_catalog, b1_states, b1_current, b1_reads, _ = simulate_full_snapshots(vintages, observations)
    b2_state = select_single_source(vintages, observations, score_by_source, scoring_source_by_observation)
    b3_arrivals, _, _, b3_current, _, b3_reads, _ = simulate_vintage_aware(
        vintages, observations, nodes, edges
    )
    b2_ids = {row["observation_id"] for row in b2_state.values()}
    return {
        "B0": {
            "serving": {row["cell_id"]: row for row in b0_state},
            "addressable": {row["requested_observation_id"] for row in b0_reads if row["available_by_vintage"] == "yes"},
        },
        "B1": {
            "serving": {row["cell_id"]: row for row in b1_current},
            "addressable": {row["requested_observation_id"] for row in b1_reads if row["available_by_snapshot"] == "yes"},
            "catalog": b1_catalog,
            "states": b1_states,
        },
        "B2": {
            "serving": b2_state,
            "addressable": {row["observation_id"] for row in observations if row["observation_id"] in b2_ids},
        },
        "B3": {
            "serving": {row["cell_id"]: row for row in b3_current},
            "addressable": {row["requested_observation_id"] for row in b3_reads if row["available_by_vintage_key"] == "yes"},
            "arrivals": b3_arrivals,
        },
    }


def _latest_by_cell(
    vintages: list[dict[str, str]], observations: list[dict[str, str]]
) -> dict[str, str]:
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    latest: dict[str, tuple[tuple[str, str, str], str]] = {}
    for row in observations:
        vintage = vintage_by_id[row["vintage_id"]]
        key = (vintage["vintage_date"], vintage["retrieved_at"], vintage["vintage_id"])
        if row["cell_id"] not in latest or key > latest[row["cell_id"]][0]:
            latest[row["cell_id"]] = (key, row["observation_id"])
    return {cell_id: observation_id for cell_id, (_, observation_id) in latest.items()}


def execute_routes(
    *,
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    scores: list[dict[str, str]],
    plans: list[dict[str, str]],
    injections: list[dict[str, str]],
    routes: list[dict[str, str]],
    manifested_states: dict[str, list[dict[str, str]]],
    harness_manifest_path: str,
    harness_manifest_sha: str,
    injections_path: str,
    injections_sha: str,
    run_id: str,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, Any],
]:
    score_by_source = {row["source_id"]: Decimal(row["trust_score"]) for row in scores}
    observation_by_id = {row["observation_id"]: row for row in observations}
    baseline = run_treatments(
        vintages=vintages,
        observations=observations,
        nodes=nodes,
        edges=edges,
        score_by_source=score_by_source,
        scoring_source_by_observation={},
    )
    baseline_mismatches = 0
    for treatment_id, manifested in manifested_states.items():
        expected = {row["cell_id"]: (row["observation_id"], row["value_lexeme"]) for row in manifested}
        replayed = {
            cell_id: (row["observation_id"], row["value_lexeme"])
            for cell_id, row in baseline[treatment_id]["serving"].items()
        }
        baseline_mismatches += sum(expected.get(cell) != value for cell, value in replayed.items())
        baseline_mismatches += len(set(expected) ^ set(replayed))
    if baseline_mismatches:
        raise ValueError("H9B baseline replay does not reproduce the manifested treatment states")

    route_rows: list[dict[str, str]] = []
    state_rows: list[dict[str, str]] = []
    recall_rows: list[dict[str, str]] = []
    synthetic_vintages: list[dict[str, str]] = []
    payload_mismatches = 0
    latest_official = max(row["vintage_date"] for row in vintages)
    for plan in sorted(plans, key=lambda row: int(row["scenario_order"])):
        scenario_id = plan["scenario_id"]
        payload = [row for row in injections if row["scenario_id"] == scenario_id]
        payload_sha = _payload_hash(payload)
        scenario_routes = {row["treatment_id"]: row for row in routes if row["scenario_id"] == scenario_id}
        if set(scenario_routes) != set(TREATMENTS):
            raise ValueError(f"H9B scenario {scenario_id} lacks a route for every treatment")
        if len({row["cell_id"] for row in payload}) != len(payload) or len(payload) != int(plan["selection_count"]):
            raise ValueError(f"H9B scenario {scenario_id} payload is not one row per selected cell")
        vintage = synthetic_vintage_row(
            vintages,
            {"scenario_id": scenario_id, "synthetic_vintage_id": plan["synthetic_vintage_id"]},
            manifest_path=harness_manifest_path,
            manifest_sha=harness_manifest_sha,
        )
        if vintage["vintage_date"] <= latest_official:
            raise ValueError("H9B synthetic vintage must be later than every official vintage")
        synthetic_vintages.append({"scenario_order": plan["scenario_order"], "scenario_id": scenario_id, **vintage})
        synthetic = synthetic_observations(
            payload,
            observation_by_id,
            artifact_path=injections_path,
            artifact_sha=injections_sha,
            run_id=run_id,
        )
        synthetic_ids = {row["observation_id"] for row in synthetic}
        scenario_vintages = [*vintages, vintage]
        scenario_observations = [*observations, *synthetic]
        scenario_nodes, scenario_edges = synthetic_lineage(nodes, edges, payload)
        executed = run_treatments(
            vintages=scenario_vintages,
            observations=scenario_observations,
            nodes=scenario_nodes,
            edges=scenario_edges,
            score_by_source=score_by_source,
            scoring_source_by_observation={
                row["synthetic_observation_id"]: row["revised_source_id"] for row in payload
            },
        )
        latest = _latest_by_cell(scenario_vintages, scenario_observations)
        source_mix = Counter(row["revised_source_id"] for row in payload)
        base_ids = {row["base_observation_id"] for row in payload}
        requests = sorted(scenario_observations, key=lambda row: row["observation_id"])
        for treatment_id in TREATMENTS:
            route = scenario_routes[treatment_id]
            verified = route["workload_sha256"] == payload_sha == plan["workload_sha256"] and route["input_rows"] == str(len(payload))
            payload_mismatches += not verified
            result = executed[treatment_id]
            before = baseline[treatment_id]["serving"]
            after = result["serving"]
            served_ids = {row["observation_id"] for row in after.values()}
            changed = [cell for cell in after if after[cell]["observation_id"] != before[cell]["observation_id"]]
            value_changed = [
                cell for cell in after if Decimal(after[cell]["value_decimal"]) != Decimal(before[cell]["value_decimal"])
            ]
            incremental_equals_full = "not_applicable"
            if treatment_id == "B0":
                evaluated, written = len(payload), len(payload)
            elif treatment_id == "B1":
                evaluated = written = int(result["catalog"][-1]["state_rows"])
            elif treatment_id == "B2":
                evaluated, written = len(payload), len(changed)
            else:
                arrival = result["arrivals"][-1]
                if arrival["vintage_id"] != vintage["vintage_id"]:
                    raise ValueError("H9B synthetic vintage is not the last B3 arrival")
                evaluated = int(arrival["recomputed_cells"])
                written = int(arrival["input_rows"]) + int(arrival["recomputed_cells"])
                incremental_equals_full = "yes" if all(row["incremental_equals_full"] == "yes" for row in result["arrivals"]) else "no"
            addressable = result["addressable"]
            route_rows.append(
                {
                    "scenario_order": plan["scenario_order"],
                    "scenario_id": scenario_id,
                    "treatment_id": treatment_id,
                    "workload_sha256": payload_sha,
                    "payload_verified": "yes" if verified else "no",
                    "input_rows": str(len(payload)),
                    "revised_source_mix": ";".join(f"{source}={count}" for source, count in sorted(source_mix.items())),
                    "single_revised_source": "yes" if len(source_mix) == 1 else "no",
                    "synthetic_vintage_id": vintage["vintage_id"],
                    "synthetic_vintage_date": vintage["vintage_date"],
                    "cells_evaluated": str(evaluated),
                    "rows_written_logical": str(written),
                    "serving_changed_cells": str(len(changed)),
                    "serving_value_changed_cells": str(len(value_changed)),
                    "synthetic_observations_served": str(len(served_ids & synthetic_ids)),
                    "latest_vintage_cells": str(sum(after[cell]["observation_id"] == latest[cell] for cell in after)),
                    "requests": str(len(requests)),
                    "addressable_requests": str(sum(row["observation_id"] in addressable for row in requests)),
                    "unavailable_requests": str(sum(row["observation_id"] not in addressable for row in requests)),
                    "revised_base_recalled": str(len(base_ids & addressable)),
                    "incremental_equals_full": incremental_equals_full,
                    "execution_status": "executed_logical",
                    "timing": "not_measured",
                    "storage": "not_measured",
                }
            )
            for cell_id in sorted(after):
                row = after[cell_id]
                state_rows.append(
                    {
                        "scenario_order": plan["scenario_order"],
                        "scenario_id": scenario_id,
                        "treatment_id": treatment_id,
                        "cell_id": cell_id,
                        "observation_id": row["observation_id"],
                        "vintage_id": row["vintage_id"],
                        "value_lexeme": row["value_lexeme"],
                        "synthetic": "yes" if row["observation_id"] in synthetic_ids else "no",
                        "changed_vs_baseline": "yes" if cell_id in changed else "no",
                    }
                )
            for request in requests:
                recall_rows.append(
                    {
                        "scenario_order": plan["scenario_order"],
                        "scenario_id": scenario_id,
                        "treatment_id": treatment_id,
                        "requested_observation_id": request["observation_id"],
                        "request_kind": "synthetic" if request["observation_id"] in synthetic_ids else "official",
                        "cell_id": request["cell_id"],
                        "addressable": "yes" if request["observation_id"] in addressable else "no",
                    }
                )
    if payload_mismatches:
        raise ValueError("H9B routes do not carry the canonical H8B scenario payload")
    return route_rows, state_rows, recall_rows, synthetic_vintages, {
        "baseline_mismatches": baseline_mismatches,
        "payload_mismatches": payload_mismatches,
    }


def _check_route_expectations(route_rows: list[dict[str, str]]) -> None:
    for row in route_rows:
        n = int(row["input_rows"])
        treatment = row["treatment_id"]
        if treatment in {"B0", "B1", "B3"} and (
            row["synthetic_observations_served"] != str(n) or row["latest_vintage_cells"] != "14"
        ):
            raise ValueError(f"H9B {treatment} does not serve every injected revision in {row['scenario_id']}")
        if treatment in {"B1", "B3"} and row["unavailable_requests"] != "0":
            raise ValueError(f"H9B {treatment} lost an addressable observation in {row['scenario_id']}")
        if treatment == "B0" and row["revised_base_recalled"] != "0":
            raise ValueError("H9B B0 must lose every revised base observation")
        if treatment == "B3" and (
            row["cells_evaluated"] != str(n) or row["incremental_equals_full"] != "yes"
        ):
            raise ValueError("H9B B3 must recompute exactly the injected cells")


def run_h9b(
    *,
    contract_path: Path,
    decisions_path: Path,
    h6_manifest_path: Path,
    h6b_manifest_path: Path,
    h6c_manifest_path: Path,
    h8b_manifest_path: Path,
    b0_manifest_path: Path,
    b1_manifest_path: Path,
    b2_manifest_path: Path,
    b3_manifest_path: Path,
    routes_output: Path,
    states_output: Path,
    recall_output: Path,
    synthetic_vintages_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    decisions = _read_csv(decisions_path)
    validate_human_decisions(decisions)

    h6 = _manifest_outputs(h6_manifest_path, {"stage": "H6", "schema_status": "validated"})
    h6b = _manifest_outputs(h6b_manifest_path, {"stage": "H6", "track": "B", "score_status": "frozen"})
    h6c = _manifest_outputs(h6c_manifest_path, {"stage": "H6", "track": "C", "lineage_status": "validated"})
    h8b = _manifest_outputs(
        h8b_manifest_path,
        {"stage": "H8", "track": "B", "harness_status": "validation_ready", "contract_version": "h8b.2"},
    )
    b0 = _manifest_outputs(b0_manifest_path, {"stage": "H7", "treatment_id": "B0", "implementation_status": "implemented"})
    b1 = _manifest_outputs(b1_manifest_path, {"stage": "H8", "track": "A", "treatment_id": "B1", "implementation_status": "implemented"})
    b2 = _manifest_outputs(b2_manifest_path, {"stage": "H7", "track": "B", "treatment_id": "B2", "implementation_status": "implemented"})
    b3 = _manifest_outputs(b3_manifest_path, {"stage": "H9", "track": "A", "treatment_id": "B3", "implementation_status": "implemented"})

    routes = _read_csv(_required(h8b, "h8b-treatment-routes.csv"))
    if {row["execution_status"] for row in routes} != {"prepared_not_run"}:
        raise ValueError("H9B expects the H8B routes in their prepared_not_run state")
    injections_path = _required(h8b, "h8b-injected-revisions.csv")
    b1_states = _read_csv(_required(b1, "h8-b1-snapshot-states.csv"))
    b1_current_order = str(max(int(row["snapshot_order"]) for row in b1_states))
    route_rows, state_rows, recall_rows, synthetic_vintages, checks = execute_routes(
        vintages=_read_csv(_required(h6, "h6-release-vintages.csv")),
        observations=_read_csv(_required(h6, "h6-indicator-observations.csv")),
        nodes=_read_csv(_required(h6c, "h6c-lineage-nodes.csv")),
        edges=_read_csv(_required(h6c, "h6c-lineage-edges.csv")),
        scores=_read_csv(_required(h6b, "h6b-source-trust-scores.csv")),
        plans=_read_csv(_required(h8b, "h8b-injection-plan.csv")),
        injections=_read_csv(injections_path),
        routes=routes,
        manifested_states={
            "B0": _read_csv(_required(b0, "h7-b0-final-state.csv")),
            "B1": [row for row in b1_states if row["snapshot_order"] == b1_current_order],
            "B2": _read_csv(_required(b2, "h7b-b2-selected-state.csv")),
            "B3": _read_csv(_required(b3, "h9-b3-current-state.csv")),
        },
        harness_manifest_path=str(h8b_manifest_path),
        harness_manifest_sha=_sha256(h8b_manifest_path),
        injections_path=str(injections_path),
        injections_sha=_sha256(injections_path),
        run_id="h9b-" + _id(_sha256(contract_path), _sha256(h8b_manifest_path)),
    )
    _check_route_expectations(route_rows)

    def total(treatment_id: str, column: str) -> int:
        return sum(int(row[column]) for row in route_rows if row["treatment_id"] == treatment_id)

    scenarios = len({row["scenario_id"] for row in route_rows})
    injected_rows = total("B0", "input_rows")
    mixed = sorted({row["scenario_id"] for row in route_rows if row["single_revised_source"] == "no"})
    metrics = {
        "scenarios": scenarios,
        "routes": len(route_rows),
        "payload_verified": sum(row["payload_verified"] == "yes" for row in route_rows),
        "payload_mismatches": checks["payload_mismatches"],
        "injected_rows": injected_rows,
        "b0_revised_base_lost": injected_rows - total("B0", "revised_base_recalled"),
        "b1_rows_written": total("B1", "rows_written_logical"),
        "b2_synthetic_served": total("B2", "synthetic_observations_served"),
        "b3_cells_recomputed": total("B3", "cells_evaluated"),
        "b1_b3_unavailable": total("B1", "unavailable_requests") + total("B3", "unavailable_requests"),
        "baseline_mismatches": checks["baseline_mismatches"],
        "mixed_source_scenarios": len(mixed),
    }
    validation = [
        {"invariant": "h9b_contract", "status": "passed", "checked_rows": "6", "detail": "input decisions synthetic ordering provenance adapters and execution boundary match h9b.1"},
        {"invariant": "human_decisions", "status": "passed", "checked_rows": str(len(decisions)), "detail": "B3 history resolution serving and synthetic ordering were approved on 2026-09-11"},
        {"invariant": "route_payload_checksums", "status": "passed", "checked_rows": str(metrics["routes"]), "detail": "every route recomputes the canonical H8B scenario payload digest"},
        {"invariant": "baseline_replay", "status": "passed", "checked_rows": "56", "detail": "replay without injection reproduces the manifested B0 B1 B2 and B3 serving states"},
        {"invariant": "synthetic_vintage_order", "status": "passed", "checked_rows": str(len(synthetic_vintages)), "detail": "each synthetic vintage is dated one day after the latest official vintage"},
        {"invariant": "synthetic_provenance", "status": "passed", "checked_rows": str(injected_rows), "detail": "synthetic rows carry the harness producer and synthetic_not_official evidence"},
        {"invariant": "revised_value_served", "status": "passed", "checked_rows": str(3 * scenarios), "detail": "B0 B1 and B3 serve every injected revision and the latest vintage in all 14 cells"},
        {"invariant": "b3_exact_recompute", "status": "passed", "checked_rows": str(scenarios), "detail": "B3 recomputes exactly the injected cells and equals a full recomputation"},
        {"invariant": "history_recall", "status": "passed", "checked_rows": str(2 * scenarios), "detail": "B1 and B3 keep every official and synthetic observation addressable"},
        {"invariant": "b0_history_loss", "status": "passed", "checked_rows": str(scenarios), "detail": f"B0 loses all {injected_rows} revised base observations"},
        {"invariant": "no_measurement_claim", "status": "passed", "checked_rows": "0", "detail": "routes executed logically; timing and storage are not measured"},
    ]
    summary = [
        {"metric": "validation_scenarios", "value": str(scenarios), "unit": "scenarios", "interpretation": "H8B validation profile 1-2-4-7-14; not the H10 freeze"},
        {"metric": "executed_routes", "value": str(metrics["routes"]), "unit": "routes", "interpretation": "five scenarios times four treatments, executed logically"},
        {"metric": "payload_verified_routes", "value": str(metrics["payload_verified"]), "unit": "routes", "interpretation": "canonical payload digest recomputed per route"},
        {"metric": "injected_rows", "value": str(injected_rows), "unit": "rows", "interpretation": "per treatment across independent scenarios"},
        {"metric": "b3_cells_recomputed", "value": str(metrics["b3_cells_recomputed"]), "unit": "cell_evaluations", "interpretation": "equals the injected cells; untouched cells are skipped"},
        {"metric": "b1_rows_written", "value": str(metrics["b1_rows_written"]), "unit": "rows", "interpretation": "one complete 14-row state per scenario regardless of revision size"},
        {"metric": "b0_revised_base_lost", "value": str(metrics["b0_revised_base_lost"]), "unit": "observations", "interpretation": "revised latest values that B0 can no longer recall"},
        {"metric": "b2_synthetic_served", "value": str(metrics["b2_synthetic_served"]), "unit": "observations", "interpretation": "injected revisions that win under the frozen source score"},
        {"metric": "b1_b3_unavailable", "value": str(metrics["b1_b3_unavailable"]), "unit": "requests", "interpretation": "must remain zero"},
        {"metric": "mixed_source_scenarios", "value": str(metrics["mixed_source_scenarios"]), "unit": "scenarios", "interpretation": f"allowed in validation only: {';'.join(mixed)}"},
        {"metric": "timed_runs", "value": "0", "unit": "runs", "interpretation": "physical and timed execution starts at H10"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (routes_output, ROUTE_COLUMNS, route_rows),
        (states_output, STATE_COLUMNS, state_rows),
        (recall_output, RECALL_COLUMNS, recall_rows),
        (synthetic_vintages_output, SYNTHETIC_VINTAGE_COLUMNS, synthetic_vintages),
        (validation_output, VALIDATION_COLUMNS, validation),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H9",
        "track": "B",
        "contract_version": contract["contract_version"],
        "execution_status": "executed_logical",
        "profile": {"status": "validation_only", "final_experiment_freeze": False, **metrics},
        "human_decisions": {
            "approved": len(decisions),
            "approved_at": "2026-09-11",
            "synthetic_vintage_ordering": contract["synthetic_vintage"]["vintage_date_rule"],
        },
        "measurement": {"timing": "not_measured", "storage": "not_measured", "physical_execution": "H10"},
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)}
            for path in (
                contract_path,
                decisions_path,
                h6_manifest_path,
                h6b_manifest_path,
                h6c_manifest_path,
                h8b_manifest_path,
                b0_manifest_path,
                b1_manifest_path,
                b2_manifest_path,
                b3_manifest_path,
            )
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**metrics, "status": "executed_logical"}
