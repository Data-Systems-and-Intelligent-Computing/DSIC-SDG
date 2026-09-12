from __future__ import annotations

import csv
import hashlib
import json
import statistics
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h6.pipeline import OBSERVATION_COLUMNS
from kkciv_vintage.h9b.pipeline import (
    SYNTHETIC_EVIDENCE,
    SYNTHETIC_SOURCE,
    _id,
    _latest_by_cell,
    _payload_hash,
    run_treatments,
    synthetic_lineage,
    synthetic_observations,
    synthetic_vintage_row,
)


TREATMENTS = ["B0", "B1", "B2", "B3"]
CLASSES = ["data", "delete", "manifest", "manifest_list", "metadata_json"]
SIZED_CLASSES = {"data", "delete", "manifest"}
PHASES = ["baseline", "after_revision"]
REQUIRED_DECISIONS = {
    "h10b_timing_environment": ("measurement", "freeze_declared_2vcpu_vm_for_all_timing"),
    "h10b_orphan_cleanup": ("stack", "remove_orphan_files_before_main_sweep"),
}
# The synthetic arrival is the fourth one; the three official releases come first.
SYNTHETIC_ARRIVAL_ORDER = "4"
SYNTHETIC_SNAPSHOT_ORDER = "4"
B2_SELECTION_COLUMNS = [
    "selected_source_id",
    "trust_score",
    "source_rank",
    "candidate_count",
    "discarded_candidate_count",
    "selected_is_latest_vintage",
    "selection_contract_version",
    "selection_run_id",
]
SCENARIO_COLUMNS = [
    "physical_order",
    "scenario_id",
    "cells",
    "revised_source_mix",
    "single_revised_source",
    "synthetic_vintage_id",
    "synthetic_vintage_date",
    "workload_sha256",
    "requests",
    "b2_expected_behaviour",
    *[f"{treatment.lower()}_expected_addressable" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_rows_written_logical" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_cells_evaluated" for treatment in TREATMENTS],
]
STORE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    *OBSERVATION_COLUMNS,
    "source_id",
    "vintage_date",
    "vintage_retrieved_at",
    "arrival_order",
]
B1_STATE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    *OBSERVATION_COLUMNS,
    "snapshot_order",
    "state_snapshot_key",
    "applied_vintage_id",
]
B2_STATE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    *OBSERVATION_COLUMNS,
    *B2_SELECTION_COLUMNS,
]
DIRTY_CELL_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "cell_id",
    "base_observation_id",
    "synthetic_observation_id",
    "impact_basis",
]
EXPECTED_STATE_COLUMNS = [
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
EXPECTED_RECALL_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "treatment_id",
    "requested_observation_id",
    "request_kind",
    "cell_id",
    "requested_value_lexeme",
    "expected_addressable",
]
TIMING_COLUMNS = [
    "repetition",
    "scenario_id",
    "treatment_id",
    "statement_index",
    "statement_label",
    "phase",
    "seconds",
]
APPLY_COST_COLUMNS = [
    "scenario_id",
    "treatment_id",
    "cells_revised",
    "cells_evaluated",
    "rows_written_logical",
    "write_statements",
    "write_seconds_median",
    "write_seconds_min",
    "write_seconds_max",
    "maintenance_seconds_median",
    "total_seconds_median",
    "baseline_bytes_median",
    "after_bytes_median",
    "delta_bytes_median",
    "delta_bytes_min",
    "delta_bytes_max",
    "delta_data_bytes_median",
    "delta_metadata_bytes_median",
    "snapshots_after",
]
STORAGE_DELTA_COLUMNS = [
    "repetition",
    "scenario_id",
    "treatment_id",
    "table",
    "baseline_objects",
    "baseline_bytes",
    "after_objects",
    "after_bytes",
    "delta_objects",
    "delta_bytes",
    "baseline_rows",
    "after_rows",
    "baseline_snapshots",
    "after_snapshots",
]
RECALL_COLUMNS = [
    "scenario_id",
    "treatment_id",
    "requested_observation_id",
    "request_kind",
    "requested_value_lexeme",
    "returned_value_lexeme",
    "locator",
    "addressable",
    "expected_addressable",
    "exact_match",
    "repetitions_agreeing",
]
ORPHAN_COLUMNS = [
    "table",
    "objects_before",
    "bytes_before",
    "objects_removed",
    "objects_after",
    "bytes_after",
    "bytes_removed",
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


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return _sha256(path)


def _lines(path: Path, prefix: str) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix + "|"):
            rows.append(line.split("|"))
    return rows


def _manifest_outputs(
    manifest_path: Path, requirements: dict[str, str]
) -> dict[str, tuple[Path, dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in requirements.items()):
        raise ValueError(f"H10B requires a valid {manifest_path} input")
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


def _median_int(values: list[int]) -> int:
    return int(statistics.median(values))


def _median_seconds(values: list[float]) -> str:
    return f"{statistics.median(values):.3f}"


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h10b.1"
        or contract.get("stage") != "H10"
        or contract.get("track") != "B"
    ):
        raise ValueError("unsupported H10B contract")
    if contract["human_decisions"]["decision_ids"] != list(REQUIRED_DECISIONS):
        raise ValueError("H10B human decisions do not match the approved registry")
    source = contract["input"]
    if (
        source["harness_contract_version"] != "h8b.2"
        or source["logical_contract_version"] != "h9b.2"
        or source["profile_status"] != "validation_only"
    ):
        raise ValueError("H10B must execute the frozen H8B payload that H9B already ran logically")
    if list(contract["tables"]) != TREATMENTS:
        raise ValueError("H10B must measure B0 B1 B2 and B3")
    if not contract["scenarios"]:
        raise ValueError("H10B needs at least one scenario")
    protocol = contract["protocol"]
    if protocol["repetitions"] < 3 or set(protocol["expected_markers"]) != set(TREATMENTS):
        raise ValueError("H10B requires at least three repetitions and a marker per treatment")
    if protocol["orphan_cleanup"]["decision_id"] != "h10b_orphan_cleanup":
        raise ValueError("H10B orphan cleanup must cite its approved decision")
    if set(protocol["injection"]) != set(TREATMENTS):
        raise ValueError("H10B needs an injection rule per treatment")
    footprint = contract["footprint"]
    if footprint["classes"] != CLASSES or footprint["phases"] != PHASES:
        raise ValueError("H10B footprint classes or phases do not match the implementation")
    timing = contract["timing"]
    if timing["environment_decision"] != "h10b_timing_environment" or not timing["claim_limit"]:
        raise ValueError("H10B timing must cite the frozen environment decision and its claim limit")
    boundary = contract["measurement_boundary"]
    if boundary["sweep_status"] != "physical_smoke_not_the_main_sweep":
        raise ValueError("H10B must not present itself as the main sweep")


def validate_human_decisions(rows: list[dict[str, str]]) -> None:
    by_id = {row["decision_id"]: row for row in rows}
    if len(by_id) != len(rows) or not set(REQUIRED_DECISIONS) <= set(by_id):
        raise ValueError("H10B requires the timing and orphan-cleanup decisions in the registry")
    for decision_id, (scope, decision) in REQUIRED_DECISIONS.items():
        row = by_id[decision_id]
        if (
            row["decided_at"] != "2026-09-12"
            or row["decided_by"] != "human_reviewer"
            or row["status"] != "approved"
            or row["scope"] != scope
            or row["decision"] != decision
            or not row["rationale"]
        ):
            raise ValueError(f"H10B human decision {decision_id} is not approved as recorded")


def b2_selection_state(
    *,
    selected: dict[str, dict[str, str]],
    observations: list[dict[str, str]],
    vintages: list[dict[str, str]],
    scores: list[dict[str, str]],
    scoring_source_by_observation: dict[str, str],
    selection_contract_version: str,
    selection_run_id: str,
) -> list[dict[str, str]]:
    """Rebuild the B2 table columns for a recomputed selection.

    The scoring source of a synthetic row is the source it revises, which is the
    frozen ``h9b_b2_synthetic_scoring`` decision. The row itself keeps its synthetic
    producer and evidence level, so no synthetic value is ever labeled as BPS data.
    """
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    score_by_source = {row["source_id"]: row for row in scores}
    candidates_by_cell: dict[str, list[dict[str, str]]] = {}
    for row in observations:
        candidates_by_cell.setdefault(row["cell_id"], []).append(row)
    latest = _latest_by_cell(vintages, observations)
    state: list[dict[str, str]] = []
    for cell_id, row in sorted(selected.items()):
        source_id = scoring_source_by_observation.get(
            row["observation_id"], vintage_by_id[row["vintage_id"]]["source_id"]
        )
        if source_id not in score_by_source:
            raise ValueError(f"H10B has no frozen score for source {source_id}")
        score = score_by_source[source_id]
        candidates = candidates_by_cell[cell_id]
        state.append(
            {
                **row,
                "selected_source_id": source_id,
                "trust_score": score["trust_score"],
                "source_rank": score["rank"],
                "candidate_count": str(len(candidates)),
                "discarded_candidate_count": str(len(candidates) - 1),
                "selected_is_latest_vintage": "true" if latest[cell_id] == row["observation_id"] else "false",
                "selection_contract_version": selection_contract_version,
                "selection_run_id": selection_run_id,
            }
        )
    return state


def prepare_scenarios(
    *,
    contract: dict[str, Any],
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    scores: list[dict[str, str]],
    plans: list[dict[str, str]],
    injections: list[dict[str, str]],
    logical_routes: list[dict[str, str]],
    logical_states: list[dict[str, str]],
    logical_recall: list[dict[str, str]],
    logical_vintages: list[dict[str, str]],
    harness_manifest_path: str,
    harness_manifest_sha: str,
    injections_path: str,
    injections_sha: str,
    logical_run_id: str,
    selection_contract_version: str,
    selection_run_id: str,
) -> dict[str, list[dict[str, str]]]:
    score_by_source = {row["source_id"]: Decimal(row["trust_score"]) for row in scores}
    observation_by_id = {row["observation_id"]: row for row in observations}
    plan_by_scenario = {row["scenario_id"]: row for row in plans}

    scenario_rows: list[dict[str, str]] = []
    store_rows: list[dict[str, str]] = []
    b1_rows: list[dict[str, str]] = []
    b2_rows: list[dict[str, str]] = []
    dirty_rows: list[dict[str, str]] = []
    expected_state_rows: list[dict[str, str]] = []
    expected_recall_rows: list[dict[str, str]] = []

    for scenario in sorted(contract["scenarios"], key=lambda row: int(row["physical_order"])):
        scenario_id = scenario["scenario_id"]
        physical_order = str(scenario["physical_order"])
        plan = plan_by_scenario.get(scenario_id)
        if plan is None:
            raise ValueError(f"H10B scenario {scenario_id} has no frozen H8B plan")
        payload = [row for row in injections if row["scenario_id"] == scenario_id]
        if len(payload) != int(scenario["cells"]) or len(payload) != int(plan["selection_count"]):
            raise ValueError(f"H10B scenario {scenario_id} payload size differs from the contract")
        payload_sha = _payload_hash(payload)
        if payload_sha != plan["workload_sha256"]:
            raise ValueError(f"H10B scenario {scenario_id} payload differs from the frozen H8B workload")
        sources = sorted({row["revised_source_id"] for row in payload})
        if sources != sorted(scenario["revised_sources"]):
            raise ValueError(f"H10B scenario {scenario_id} revises other sources than the contract states")

        vintage = synthetic_vintage_row(
            vintages,
            {"scenario_id": scenario_id, "synthetic_vintage_id": plan["synthetic_vintage_id"]},
            manifest_path=harness_manifest_path,
            manifest_sha=harness_manifest_sha,
        )
        frozen_vintage = next(
            (row for row in logical_vintages if row["scenario_id"] == scenario_id), None
        )
        if frozen_vintage is None or any(
            frozen_vintage[key] != value for key, value in vintage.items()
        ):
            raise ValueError(f"H10B synthetic vintage for {scenario_id} differs from the H9B run")
        synthetic = synthetic_observations(
            payload,
            observation_by_id,
            artifact_path=injections_path,
            artifact_sha=injections_sha,
            run_id=logical_run_id,
        )
        synthetic_by_id = {row["observation_id"]: row for row in synthetic}
        scenario_vintages = [*vintages, vintage]
        scenario_observations = [*observations, *synthetic]
        scenario_nodes, scenario_edges = synthetic_lineage(nodes, edges, payload)
        scoring_source_by_observation = {
            row["synthetic_observation_id"]: row["revised_source_id"] for row in payload
        }
        executed = run_treatments(
            vintages=scenario_vintages,
            observations=scenario_observations,
            nodes=scenario_nodes,
            edges=scenario_edges,
            score_by_source=score_by_source,
            scoring_source_by_observation=scoring_source_by_observation,
        )

        # The physical payload only ships if it reproduces the frozen logical result.
        frozen_states = {
            (row["treatment_id"], row["cell_id"]): row
            for row in logical_states
            if row["scenario_id"] == scenario_id
        }
        for treatment_id in TREATMENTS:
            serving = executed[treatment_id]["serving"]
            for cell_id, row in sorted(serving.items()):
                frozen = frozen_states.get((treatment_id, cell_id))
                if frozen is None or frozen["observation_id"] != row["observation_id"] or frozen["value_lexeme"] != row["value_lexeme"]:
                    raise ValueError(
                        f"H10B recomputed {treatment_id} state for {scenario_id} differs from the H9B state"
                    )
                expected_state_rows.append(
                    {
                        "scenario_order": physical_order,
                        "scenario_id": scenario_id,
                        "treatment_id": treatment_id,
                        "cell_id": cell_id,
                        "observation_id": row["observation_id"],
                        "vintage_id": row["vintage_id"],
                        "value_lexeme": row["value_lexeme"],
                        "synthetic": frozen["synthetic"],
                        "changed_vs_baseline": frozen["changed_vs_baseline"],
                    }
                )

        for row in sorted(synthetic, key=lambda item: item["observation_id"]):
            store_rows.append(
                {
                    "scenario_order": physical_order,
                    "scenario_id": scenario_id,
                    **row,
                    "source_id": SYNTHETIC_SOURCE,
                    "vintage_date": vintage["vintage_date"],
                    "vintage_retrieved_at": vintage["retrieved_at"],
                    "arrival_order": SYNTHETIC_ARRIVAL_ORDER,
                }
            )

        next_state = [
            row for row in executed["B1"]["states"] if row["snapshot_order"] == SYNTHETIC_SNAPSHOT_ORDER
        ]
        if len(next_state) != len(executed["B1"]["serving"]):
            raise ValueError(f"H10B B1 next state for {scenario_id} is not a complete state")
        for row in sorted(next_state, key=lambda item: item["cell_id"]):
            b1_rows.append({"scenario_order": physical_order, "scenario_id": scenario_id, **row})

        for row in b2_selection_state(
            selected=executed["B2"]["serving"],
            observations=scenario_observations,
            vintages=scenario_vintages,
            scores=scores,
            scoring_source_by_observation=scoring_source_by_observation,
            selection_contract_version=selection_contract_version,
            selection_run_id=selection_run_id,
        ):
            b2_rows.append({"scenario_order": physical_order, "scenario_id": scenario_id, **row})

        for injection in sorted(payload, key=lambda row: row["cell_id"]):
            dirty_rows.append(
                {
                    "scenario_order": physical_order,
                    "scenario_id": scenario_id,
                    "cell_id": injection["cell_id"],
                    "base_observation_id": injection["base_observation_id"],
                    "synthetic_observation_id": injection["synthetic_observation_id"],
                    "impact_basis": "synthetic revision inherits the H6C cell edge of its base observation",
                }
            )

        frozen_recall = [row for row in logical_recall if row["scenario_id"] == scenario_id]
        if len(frozen_recall) != len(scenario_observations) * len(TREATMENTS):
            raise ValueError(f"H10B has no complete H9B recall audit for {scenario_id}")
        lexeme_by_id = {
            row["observation_id"]: row["value_lexeme"]
            for row in scenario_observations
        }
        for row in frozen_recall:
            expected_recall_rows.append(
                {
                    "scenario_order": physical_order,
                    "scenario_id": scenario_id,
                    "treatment_id": row["treatment_id"],
                    "requested_observation_id": row["requested_observation_id"],
                    "request_kind": row["request_kind"],
                    "cell_id": row["cell_id"],
                    "requested_value_lexeme": lexeme_by_id[row["requested_observation_id"]],
                    "expected_addressable": row["addressable"],
                }
            )

        routes = {
            row["treatment_id"]: row
            for row in logical_routes
            if row["scenario_id"] == scenario_id
        }
        if set(routes) != set(TREATMENTS):
            raise ValueError(f"H10B has no logical route for every treatment of {scenario_id}")
        served = int(routes["B2"]["synthetic_observations_served"])
        if served == 0:
            b2_behaviour = "withhold"
        elif served == len(payload):
            b2_behaviour = "propagate_all"
        else:
            b2_behaviour = f"propagate_{served}_of_{len(payload)}"
        expected_behaviour = {"propagate_one_of_two": "propagate_1_of_2"}.get(
            scenario["b2_expected_behaviour"], scenario["b2_expected_behaviour"]
        )
        if expected_behaviour != b2_behaviour:
            raise ValueError(
                f"H10B contract expects B2 to {expected_behaviour} in {scenario_id}, logical run says {b2_behaviour}"
            )
        scenario_rows.append(
            {
                "physical_order": physical_order,
                "scenario_id": scenario_id,
                "cells": str(len(payload)),
                "revised_source_mix": routes["B0"]["revised_source_mix"],
                "single_revised_source": routes["B0"]["single_revised_source"],
                "synthetic_vintage_id": vintage["vintage_id"],
                "synthetic_vintage_date": vintage["vintage_date"],
                "workload_sha256": payload_sha,
                "requests": str(len(scenario_observations)),
                "b2_expected_behaviour": b2_behaviour,
                **{
                    f"{treatment.lower()}_expected_addressable": routes[treatment]["addressable_requests"]
                    for treatment in TREATMENTS
                },
                **{
                    f"{treatment.lower()}_rows_written_logical": routes[treatment]["rows_written_logical"]
                    for treatment in TREATMENTS
                },
                **{
                    f"{treatment.lower()}_cells_evaluated": routes[treatment]["cells_evaluated"]
                    for treatment in TREATMENTS
                },
            }
        )
        if any(row["evidence_level"] != SYNTHETIC_EVIDENCE or row["producer"] != SYNTHETIC_SOURCE for row in synthetic_by_id.values()):
            raise ValueError("H10B synthetic rows must never masquerade as official BPS data")

    return {
        "scenarios": scenario_rows,
        "store": store_rows,
        "b1": b1_rows,
        "b2": b2_rows,
        "dirty": dirty_rows,
        "expected_state": expected_state_rows,
        "expected_recall": expected_recall_rows,
    }


def run_prepare(
    *,
    contract_path: Path,
    decisions_path: Path,
    h6_manifest_path: Path,
    h6b_manifest_path: Path,
    h6c_manifest_path: Path,
    h8b_manifest_path: Path,
    h9b_contract_path: Path,
    h9b_manifest_path: Path,
    b2_contract_path: Path,
    scenarios_output: Path,
    store_output: Path,
    b1_output: Path,
    b2_output: Path,
    dirty_output: Path,
    expected_state_output: Path,
    expected_recall_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_human_decisions(_read_csv(decisions_path))

    h6 = _manifest_outputs(h6_manifest_path, {"stage": "H6", "schema_status": "validated"})
    h6b = _manifest_outputs(h6b_manifest_path, {"stage": "H6", "track": "B", "score_status": "frozen"})
    h6c = _manifest_outputs(h6c_manifest_path, {"stage": "H6", "track": "C", "lineage_status": "validated"})
    h8b = _manifest_outputs(
        h8b_manifest_path, {"stage": "H8", "track": "B", "harness_status": "validation_ready"}
    )
    h9b = _manifest_outputs(
        h9b_manifest_path, {"stage": "H9", "track": "B", "execution_status": "executed_logical"}
    )
    injections_path = _required(h8b, "h8b-injected-revisions.csv")
    b2_contract = json.loads(b2_contract_path.read_text(encoding="utf-8"))

    prepared = prepare_scenarios(
        contract=contract,
        vintages=_read_csv(_required(h6, "h6-release-vintages.csv")),
        observations=_read_csv(_required(h6, "h6-indicator-observations.csv")),
        nodes=_read_csv(_required(h6c, "h6c-lineage-nodes.csv")),
        edges=_read_csv(_required(h6c, "h6c-lineage-edges.csv")),
        scores=_read_csv(_required(h6b, "h6b-source-trust-scores.csv")),
        plans=_read_csv(_required(h8b, "h8b-injection-plan.csv")),
        injections=_read_csv(injections_path),
        logical_routes=_read_csv(_required(h9b, "h9b-route-executions.csv")),
        logical_states=_read_csv(_required(h9b, "h9b-post-revision-states.csv")),
        logical_recall=_read_csv(_required(h9b, "h9b-recall-audit.csv")),
        logical_vintages=_read_csv(_required(h9b, "h9b-synthetic-vintages.csv")),
        harness_manifest_path=str(h8b_manifest_path),
        harness_manifest_sha=_sha256(h8b_manifest_path),
        injections_path=str(injections_path),
        injections_sha=_sha256(injections_path),
        logical_run_id="h9b-" + _id(_sha256(h9b_contract_path), _sha256(h8b_manifest_path)),
        selection_contract_version=b2_contract["contract_version"],
        selection_run_id="h10b-" + _id(_sha256(contract_path), _sha256(h9b_manifest_path)),
    )

    written_outputs = []
    for path, columns, rows in (
        (scenarios_output, SCENARIO_COLUMNS, prepared["scenarios"]),
        (store_output, STORE_COLUMNS, prepared["store"]),
        (b1_output, B1_STATE_COLUMNS, prepared["b1"]),
        (b2_output, B2_STATE_COLUMNS, prepared["b2"]),
        (dirty_output, DIRTY_CELL_COLUMNS, prepared["dirty"]),
        (expected_state_output, EXPECTED_STATE_COLUMNS, prepared["expected_state"]),
        (expected_recall_output, EXPECTED_RECALL_COLUMNS, prepared["expected_recall"]),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H10",
        "track": "B",
        "contract_version": contract["contract_version"],
        "payload_status": "prepared",
        "scenarios": [
            {key: row[key] for key in ("physical_order", "scenario_id", "cells", "workload_sha256", "synthetic_vintage_id")}
            for row in prepared["scenarios"]
        ],
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)}
            for path in (
                contract_path,
                decisions_path,
                h6_manifest_path,
                h6b_manifest_path,
                h6c_manifest_path,
                h8b_manifest_path,
                h9b_contract_path,
                h9b_manifest_path,
                b2_contract_path,
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
        "scenarios": len(prepared["scenarios"]),
        "synthetic_rows": len(prepared["store"]),
        "expected_states": len(prepared["expected_state"]),
        "expected_requests": len(prepared["expected_recall"]),
    }


def read_environment(path: Path) -> dict[str, str]:
    environment = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        environment[key] = value
    return environment


def audit_orphan_cleanup(lines: list[list[str]], removals: list[list[str]]) -> list[dict[str, str]]:
    before = {row[1]: row for row in lines if row[2] == "before"}
    after = {row[1]: row for row in lines if row[2] == "after"}
    if not before or set(before) != set(after):
        raise ValueError("H10B orphan cleanup did not list every table before and after")
    removed_by_table: dict[str, int] = {table: 0 for table in before}
    for row in removals:
        if row[1] not in removed_by_table:
            raise ValueError(f"H10B removed an orphan file of an unknown table {row[1]}")
        removed_by_table[row[1]] += 1
    rows: list[dict[str, str]] = []
    for table in sorted(before):
        objects_before, bytes_before = int(before[table][3]), int(before[table][4])
        objects_after, bytes_after = int(after[table][3]), int(after[table][4])
        if objects_before - objects_after != removed_by_table[table]:
            raise ValueError(f"H10B orphan cleanup of {table} removed a different number of objects than it reported")
        if bytes_after > bytes_before:
            raise ValueError(f"H10B orphan cleanup of {table} did not shrink the table location")
        rows.append(
            {
                "table": table,
                "objects_before": str(objects_before),
                "bytes_before": str(bytes_before),
                "objects_removed": str(removed_by_table[table]),
                "objects_after": str(objects_after),
                "bytes_after": str(bytes_after),
                "bytes_removed": str(bytes_before - bytes_after),
            }
        )
    return rows


def measure_phases(
    *,
    contract: dict[str, Any],
    footprint_lines: list[list[str]],
    state_lines: list[list[str]],
    listing_lines: list[list[str]],
    scenarios: list[str],
) -> list[dict[str, str]]:
    """Fold the per-object rows into one baseline-versus-after row per table."""
    expected_tables = {
        (treatment, table) for treatment, tables in contract["tables"].items() for table in tables
    }
    repetitions = [str(rep) for rep in range(1, contract["protocol"]["repetitions"] + 1)]
    listing: dict[tuple[str, str, str, str], dict[str, int]] = {}
    for _, rep, scenario, phase, _treatment, table, path, size in listing_lines:
        listing.setdefault((rep, scenario, phase, table), {})[path] = int(size)
    states = {
        (rep, scenario, phase, table): (snapshots, rows)
        for _, rep, scenario, phase, _treatment, table, snapshots, rows in state_lines
    }

    # object path -> (size, object class); a path is reachable at most once per class.
    reachable: dict[tuple[str, str, str, str], dict[str, tuple[int, str]]] = {}
    for (
        _,
        rep,
        scenario,
        phase,
        treatment,
        table,
        object_class,
        path,
        metadata_size,
        _records,
    ) in footprint_lines:
        if (treatment, table) not in expected_tables or rep not in repetitions or scenario not in scenarios:
            raise ValueError(f"unexpected H10B footprint row for {treatment} {table} rep {rep}")
        if phase not in PHASES or object_class not in CLASSES:
            raise ValueError(f"unexpected H10B footprint phase {phase} or class {object_class}")
        objects = listing.get((rep, scenario, phase, table), {})
        if path not in objects:
            raise ValueError(f"metadata references a missing object {path}")
        if object_class in SIZED_CLASSES and int(metadata_size) != objects[path]:
            raise ValueError(f"metadata size differs from the MinIO object size for {path}")
        reachable.setdefault((rep, scenario, phase, table), {})[path] = (objects[path], object_class)

    rows: list[dict[str, str]] = []
    for rep in repetitions:
        for scenario in scenarios:
            for treatment, table in sorted(
                expected_tables, key=lambda item: (TREATMENTS.index(item[0]), item[1])
            ):
                phase_values = {}
                for phase in PHASES:
                    key = (rep, scenario, phase, table)
                    if key not in reachable or key not in states:
                        raise ValueError(f"H10B has no {phase} measurement for {table} rep {rep} {scenario}")
                    objects = reachable[key]
                    phase_values[phase] = {
                        "objects": len(objects),
                        "bytes": sum(size for size, _ in objects.values()),
                        "data_bytes": sum(
                            size for size, object_class in objects.values() if object_class in {"data", "delete"}
                        ),
                        "snapshots": states[key][0],
                        "rows": states[key][1],
                    }
                baseline, after = phase_values["baseline"], phase_values["after_revision"]
                rows.append(
                    {
                        "repetition": rep,
                        "scenario_id": scenario,
                        "treatment_id": treatment,
                        "table": table,
                        "baseline_objects": str(baseline["objects"]),
                        "baseline_bytes": str(baseline["bytes"]),
                        "after_objects": str(after["objects"]),
                        "after_bytes": str(after["bytes"]),
                        "delta_objects": str(after["objects"] - baseline["objects"]),
                        "delta_bytes": str(after["bytes"] - baseline["bytes"]),
                        "baseline_rows": baseline["rows"],
                        "after_rows": after["rows"],
                        "baseline_snapshots": baseline["snapshots"],
                        "after_snapshots": after["snapshots"],
                        "baseline_data_bytes": str(baseline["data_bytes"]),
                        "after_data_bytes": str(after["data_bytes"]),
                    }
                )
    return rows


def audit_injection(
    *,
    lines: list[list[str]],
    contract: dict[str, Any],
    scenarios: list[dict[str, str]],
    official_requests: int,
) -> list[dict[str, str]]:
    repetitions = [str(rep) for rep in range(1, contract["protocol"]["repetitions"] + 1)]
    cells_by_scenario = {row["scenario_id"]: int(row["cells"]) for row in scenarios}
    rows: list[dict[str, str]] = []
    seen = set()
    for _, rep, scenario, treatment, served_rows, cells, snapshots, mismatches, store_rows, store_snapshots in lines:
        if rep not in repetitions or scenario not in cells_by_scenario or treatment not in TREATMENTS:
            raise ValueError(f"unexpected H10B injection row for {treatment} rep {rep} {scenario}")
        if (rep, scenario, treatment) in seen:
            raise ValueError(f"H10B injected {treatment} twice in rep {rep} {scenario}")
        seen.add((rep, scenario, treatment))
        if mismatches != "0":
            raise ValueError(f"H10B {treatment} state after {scenario} differs from the logical H9B state")
        if served_rows != cells or served_rows != "14":
            raise ValueError(f"H10B {treatment} serves {served_rows} rows over {cells} cells instead of 14")
        expected_snapshots = "4" if treatment == "B1" else "1"
        if snapshots != expected_snapshots:
            raise ValueError(f"H10B {treatment} retains {snapshots} snapshots instead of {expected_snapshots}")
        if treatment == "B3":
            if store_rows != str(official_requests + cells_by_scenario[scenario]):
                raise ValueError(f"H10B B3 store holds {store_rows} rows after {scenario}")
            if store_snapshots != "1":
                raise ValueError("H10B B3 store must keep exactly one snapshot")
        rows.append(
            {
                "repetition": rep,
                "scenario_id": scenario,
                "treatment_id": treatment,
                "served_rows": served_rows,
                "served_cells": cells,
                "snapshots": snapshots,
                "store_rows": store_rows,
                "store_snapshots": store_snapshots,
            }
        )
    if len(seen) != len(repetitions) * len(cells_by_scenario) * len(TREATMENTS):
        raise ValueError("H10B did not inject every treatment in every repetition and scenario")
    return rows


def audit_recall(
    *,
    lines: list[list[str]],
    expected: list[dict[str, str]],
    snapshot_counts: list[list[str]],
    repetitions: int,
) -> list[dict[str, str]]:
    expected_by_key = {
        (row["scenario_id"], row["treatment_id"], row["requested_observation_id"]): row
        for row in expected
    }
    for _, _rep, scenario, count in snapshot_counts:
        if count != "4":
            raise ValueError(f"H10B B1 must expose four snapshots in {scenario}, found {count}")
    observed: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for _, rep, scenario, treatment, request_id, returned_id, returned_lexeme, locator in lines:
        key = (scenario, treatment, request_id)
        if key not in expected_by_key:
            raise ValueError(f"H10B recalled an unexpected request {request_id} for {treatment} {scenario}")
        expectation = expected_by_key[key]
        addressable = returned_id == request_id
        if returned_id and not addressable:
            raise ValueError(f"H10B {treatment} returned a different observation for {request_id}")
        if addressable and returned_lexeme != expectation["requested_value_lexeme"]:
            raise ValueError(f"H10B {treatment} returned a different value for {request_id}")
        if ("yes" if addressable else "no") != expectation["expected_addressable"]:
            raise ValueError(
                f"H10B {treatment} recall of {request_id} in {scenario} disagrees with the logical H9B audit"
            )
        observed.setdefault(key, []).append(
            {
                "repetition": rep,
                "returned_value_lexeme": returned_lexeme,
                "locator": locator if addressable else "",
                "addressable": "yes" if addressable else "no",
            }
        )
    if set(observed) != set(expected_by_key):
        raise ValueError("H10B recall does not cover every expected request")

    rows: list[dict[str, str]] = []
    for key, results in observed.items():
        if len(results) != repetitions:
            raise ValueError(f"H10B recall of {key} was not repeated {repetitions} times")
        if len({(row["addressable"], row["returned_value_lexeme"]) for row in results}) != 1:
            raise ValueError(f"H10B repetitions disagree about the recall of {key}")
        scenario, treatment, request_id = key
        expectation = expected_by_key[key]
        first = results[0]
        addressable = first["addressable"] == "yes"
        rows.append(
            {
                "scenario_id": scenario,
                "treatment_id": treatment,
                "requested_observation_id": request_id,
                "request_kind": expectation["request_kind"],
                "requested_value_lexeme": expectation["requested_value_lexeme"],
                "returned_value_lexeme": first["returned_value_lexeme"],
                "locator": first["locator"],
                "addressable": first["addressable"],
                "expected_addressable": expectation["expected_addressable"],
                "exact_match": "yes" if addressable and first["returned_value_lexeme"] == expectation["requested_value_lexeme"] else "not_applicable",
                "repetitions_agreeing": str(len(results)),
            }
        )
    rows.sort(
        key=lambda row: (row["scenario_id"], TREATMENTS.index(row["treatment_id"]), row["requested_observation_id"])
    )
    return rows


def aggregate_apply_cost(
    *,
    timing_rows: list[dict[str, str]],
    storage_rows: list[dict[str, str]],
    scenarios: list[dict[str, str]],
    repetitions: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for scenario in sorted(scenarios, key=lambda row: int(row["physical_order"])):
        scenario_id = scenario["scenario_id"]
        for treatment in TREATMENTS:
            write_seconds: list[float] = []
            maintenance_seconds: list[float] = []
            total_bytes: list[int] = []
            data_bytes: list[int] = []
            baseline_bytes: list[int] = []
            after_bytes: list[int] = []
            snapshots: set[str] = set()
            write_statements: set[int] = set()
            for rep in [str(index) for index in range(1, repetitions + 1)]:
                timed = [
                    row
                    for row in timing_rows
                    if row["repetition"] == rep
                    and row["scenario_id"] == scenario_id
                    and row["treatment_id"] == treatment
                ]
                if not timed:
                    raise ValueError(f"H10B has no timing for {treatment} in rep {rep} {scenario_id}")
                write = [row for row in timed if row["phase"] == "write"]
                write_statements.add(len(write))
                write_seconds.append(sum(float(row["seconds"]) for row in write))
                maintenance_seconds.append(
                    sum(float(row["seconds"]) for row in timed if row["phase"] == "maintenance")
                )
                tables = [
                    row
                    for row in storage_rows
                    if row["repetition"] == rep
                    and row["scenario_id"] == scenario_id
                    and row["treatment_id"] == treatment
                ]
                if not tables:
                    raise ValueError(f"H10B has no storage delta for {treatment} in rep {rep} {scenario_id}")
                total_bytes.append(sum(int(row["delta_bytes"]) for row in tables))
                data_bytes.append(
                    sum(int(row["after_data_bytes"]) - int(row["baseline_data_bytes"]) for row in tables)
                )
                baseline_bytes.append(sum(int(row["baseline_bytes"]) for row in tables))
                after_bytes.append(sum(int(row["after_bytes"]) for row in tables))
                snapshots.add("+".join(row["after_snapshots"] for row in tables))
            if len(write_statements) != 1 or len(snapshots) != 1:
                raise ValueError(f"H10B {treatment} wrote a different shape across repetitions in {scenario_id}")
            delta_median = _median_int(total_bytes)
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "treatment_id": treatment,
                    "cells_revised": scenario["cells"],
                    "cells_evaluated": scenario[f"{treatment.lower()}_cells_evaluated"],
                    "rows_written_logical": scenario[f"{treatment.lower()}_rows_written_logical"],
                    "write_statements": str(write_statements.pop()),
                    "write_seconds_median": _median_seconds(write_seconds),
                    "write_seconds_min": f"{min(write_seconds):.3f}",
                    "write_seconds_max": f"{max(write_seconds):.3f}",
                    "maintenance_seconds_median": _median_seconds(maintenance_seconds),
                    "total_seconds_median": _median_seconds(
                        [write + maintenance for write, maintenance in zip(write_seconds, maintenance_seconds)]
                    ),
                    "baseline_bytes_median": str(_median_int(baseline_bytes)),
                    "after_bytes_median": str(_median_int(after_bytes)),
                    "delta_bytes_median": str(delta_median),
                    "delta_bytes_min": str(min(total_bytes)),
                    "delta_bytes_max": str(max(total_bytes)),
                    "delta_data_bytes_median": str(_median_int(data_bytes)),
                    "delta_metadata_bytes_median": str(delta_median - _median_int(data_bytes)),
                    "snapshots_after": snapshots.pop(),
                }
            )
    return rows


def run_aggregate(
    *,
    contract_path: Path,
    decisions_path: Path,
    raw_dir: Path,
    cleanup_dir: Path,
    payload_manifest_path: Path,
    timing_output: Path,
    apply_cost_output: Path,
    storage_output: Path,
    recall_output: Path,
    orphan_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    decisions = _read_csv(decisions_path)
    validate_human_decisions(decisions)

    payload = _manifest_outputs(
        payload_manifest_path, {"stage": "H10", "track": "B", "payload_status": "prepared"}
    )
    scenarios = _read_csv(_required(payload, "h10b-physical-scenarios.csv"))
    expected_recall = _read_csv(_required(payload, "h10b-expected-recall.csv"))
    scenario_ids = [row["scenario_id"] for row in sorted(scenarios, key=lambda row: int(row["physical_order"]))]
    if scenario_ids != [row["scenario_id"] for row in sorted(contract["scenarios"], key=lambda row: int(row["physical_order"]))]:
        raise ValueError("H10B payload scenarios differ from the contract")
    repetitions = contract["protocol"]["repetitions"]

    environment = read_environment(raw_dir / "environment.txt")
    if not environment.get("catalog_uri", "").startswith(contract["protocol"]["catalog_uri_prefix"]):
        raise ValueError("H10B measurement ran without the persistent catalog")
    if environment.get("git_dirty_entries") != "0":
        raise ValueError("H10B measurement started from a dirty working tree")
    if environment.get("repetitions") != str(repetitions):
        raise ValueError("H10B raw run used a different repetition count")
    if environment.get("scenarios") != ";".join(scenario_ids):
        raise ValueError("H10B raw run measured other scenarios than the payload")

    markers = [
        line.split("|", 3)
        for line in (raw_dir / "apply-markers.txt").read_text(encoding="utf-8").splitlines()
    ]
    expected_markers = contract["protocol"]["expected_markers"]
    for rep, scenario, treatment, marker in markers:
        if scenario not in scenario_ids or marker != expected_markers[treatment]:
            raise ValueError(f"H10B rep {rep} {scenario} {treatment} marker {marker} differs from the recorded marker")
    if len(markers) != repetitions * len(scenario_ids) * len(TREATMENTS):
        raise ValueError("H10B baseline apply markers are incomplete")

    orphan_rows = audit_orphan_cleanup(
        _lines(cleanup_dir / "orphan-cleanup.txt", "H10BC"),
        _lines(cleanup_dir / "orphan-cleanup.txt", "H10BO"),
    )
    verification = _lines(raw_dir / "orphan-verification.txt", "H10BV")
    if len(verification) != len(orphan_rows) or any(row[2] != "0" for row in verification):
        raise ValueError("H10B started before every table was verified free of orphan files")

    storage_rows = measure_phases(
        contract=contract,
        footprint_lines=_lines(raw_dir / "footprint.txt", "H10F"),
        state_lines=_lines(raw_dir / "footprint.txt", "H10S"),
        listing_lines=_lines(raw_dir / "listing.txt", "H10L"),
        scenarios=scenario_ids,
    )
    timing_rows = [
        {
            "repetition": rep,
            "scenario_id": scenario,
            "treatment_id": treatment,
            "statement_index": index,
            "statement_label": label,
            "phase": phase,
            "seconds": seconds,
        }
        for _, rep, scenario, treatment, index, label, phase, seconds in _lines(raw_dir / "timing.txt", "H10BT")
    ]
    official_requests = len(
        [
            row
            for row in expected_recall
            if row["scenario_id"] == scenario_ids[0]
            and row["treatment_id"] == "B0"
            and row["request_kind"] == "official"
        ]
    )
    injection_rows = audit_injection(
        lines=_lines(raw_dir / "injection.txt", "H10BI"),
        contract=contract,
        scenarios=scenarios,
        official_requests=official_requests,
    )
    recall_rows = audit_recall(
        lines=_lines(raw_dir / "recall.txt", "H10BR"),
        expected=expected_recall,
        snapshot_counts=_lines(raw_dir / "recall.txt", "H10BSNAPCOUNT"),
        repetitions=repetitions,
    )
    cost_rows = aggregate_apply_cost(
        timing_rows=timing_rows,
        storage_rows=storage_rows,
        scenarios=scenarios,
        repetitions=repetitions,
    )

    first_scenario = scenario_ids[0]
    cost_by_key = {(row["scenario_id"], row["treatment_id"]): row for row in cost_rows}
    recalled = {
        (row["scenario_id"], row["treatment_id"]): sum(
            other["addressable"] == "yes"
            for other in recall_rows
            if other["scenario_id"] == row["scenario_id"] and other["treatment_id"] == row["treatment_id"]
        )
        for row in recall_rows
    }
    orphan_bytes = sum(int(row["bytes_removed"]) for row in orphan_rows)
    orphan_objects = sum(int(row["objects_removed"]) for row in orphan_rows)

    validation = [
        {"invariant": "h10b_contract", "status": "passed", "checked_rows": "7", "detail": "decisions scenarios tables protocol timing footprint and boundary match h10b.1"},
        {"invariant": "human_decisions", "status": "passed", "checked_rows": str(len(decisions)), "detail": "timing environment and orphan cleanup approved on 2026-09-12"},
        {"invariant": "persistent_catalog", "status": "passed", "checked_rows": "1", "detail": environment["catalog_uri"]},
        {"invariant": "clean_start", "status": "passed", "checked_rows": "1", "detail": f"git commit {environment['git_commit']} with no local changes"},
        {"invariant": "orphan_cleanup_before_run", "status": "passed", "checked_rows": str(len(orphan_rows)), "detail": f"{orphan_objects} objects and {orphan_bytes} bytes removed once; a dry run found nothing left in any table"},
        {"invariant": "baseline_markers", "status": "passed", "checked_rows": str(len(markers)), "detail": "every rebuild reproduces the recorded B0 B1 B2 and B3 verification markers"},
        {"invariant": "physical_equals_logical_state", "status": "passed", "checked_rows": str(len(injection_rows)), "detail": "every post-revision table equals the logical H9B state of its scenario"},
        {"invariant": "objects_exist_with_metadata_size", "status": "passed", "checked_rows": str(len(storage_rows)), "detail": "every referenced object exists in MinIO; data delete and manifest sizes equal their metadata"},
        {"invariant": "retained_snapshots", "status": "passed", "checked_rows": str(len(injection_rows)), "detail": "B1 keeps four snapshots; B0 B2 and both B3 tables keep one"},
        {"invariant": "physical_equals_logical_recall", "status": "passed", "checked_rows": str(len(recall_rows)), "detail": "every request agrees with the H9B recall audit in all repetitions"},
        {"invariant": "timing_environment_declared", "status": "passed", "checked_rows": str(len(timing_rows)), "detail": f"statement times measured on {environment['host_nproc']} vCPU and {environment['spark_driver_memory']} driver memory; comparative only"},
    ]
    summary = [
        {"metric": "repetitions", "value": str(repetitions), "unit": "runs", "interpretation": "serial rebuild-inject-measure cycles per scenario"},
        {"metric": "scenarios", "value": str(len(scenario_ids)), "unit": "scenarios", "interpretation": "frozen H8B validation payloads; not the main sweep profile"},
        {"metric": "orphan_bytes_removed", "value": str(orphan_bytes), "unit": "bytes", "interpretation": f"{orphan_objects} objects removed once before the run"},
        {"metric": "host_nproc", "value": environment["host_nproc"], "unit": "vCPU", "interpretation": "declared timing environment, frozen on 2026-09-12"},
    ]
    for row in cost_rows:
        summary.append(
            {
                "metric": f"{row['treatment_id'].lower()}_{row['scenario_id']}_write_seconds_median",
                "value": row["write_seconds_median"],
                "unit": "seconds",
                "interpretation": f"range {row['write_seconds_min']}-{row['write_seconds_max']}; maintenance {row['maintenance_seconds_median']}; {row['write_statements']} write statements",
            }
        )
        summary.append(
            {
                "metric": f"{row['treatment_id'].lower()}_{row['scenario_id']}_delta_bytes_median",
                "value": row["delta_bytes_median"],
                "unit": "bytes",
                "interpretation": f"range {row['delta_bytes_min']}-{row['delta_bytes_max']}; data {row['delta_data_bytes_median']}; metadata {row['delta_metadata_bytes_median']}",
            }
        )
    for scenario_id in scenario_ids:
        for treatment in TREATMENTS:
            summary.append(
                {
                    "metric": f"{treatment.lower()}_{scenario_id}_recalled",
                    "value": str(recalled[(scenario_id, treatment)]),
                    "unit": "requests",
                    "interpretation": "official and synthetic observations returned with the exact value after the revision",
                }
            )

    written_outputs = []
    for path, columns, rows in (
        (timing_output, TIMING_COLUMNS, timing_rows),
        (apply_cost_output, APPLY_COST_COLUMNS, cost_rows),
        (storage_output, STORAGE_DELTA_COLUMNS, storage_rows),
        (recall_output, RECALL_COLUMNS, recall_rows),
        (orphan_output, ORPHAN_COLUMNS, orphan_rows),
        (validation_output, VALIDATION_COLUMNS, validation),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    raw_files = sorted(
        path for path in [*raw_dir.rglob("*"), *cleanup_dir.rglob("*")] if path.is_file()
    )
    manifest = {
        "stage": "H10",
        "track": "B",
        "contract_version": contract["contract_version"],
        "execution_status": "executed_physical",
        "environment": environment,
        "orphan_cleanup": {"objects_removed": orphan_objects, "bytes_removed": orphan_bytes},
        "apply_cost": {
            f"{row['scenario_id']}|{row['treatment_id']}": {
                key: row[key]
                for key in (
                    "write_seconds_median",
                    "maintenance_seconds_median",
                    "delta_bytes_median",
                    "snapshots_after",
                )
            }
            for row in cost_rows
        },
        "recall_after_revision": {
            f"{scenario_id}|{treatment}": recalled[(scenario_id, treatment)]
            for scenario_id in scenario_ids
            for treatment in TREATMENTS
        },
        "measurement": contract["measurement_boundary"],
        "raw_inputs": [{"path": str(path), "sha256": _sha256(path)} for path in raw_files],
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)}
            for path in (contract_path, decisions_path, payload_manifest_path)
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "repetitions": repetitions,
        "scenarios": len(scenario_ids),
        "routes": len(cost_rows),
        "requests": len(recall_rows),
        "orphan_objects": orphan_objects,
        "orphan_bytes": orphan_bytes,
        "first_scenario": first_scenario,
        "write_seconds": {
            treatment: cost_by_key[(first_scenario, treatment)]["write_seconds_median"]
            for treatment in TREATMENTS
        },
        "delta_bytes": {
            treatment: cost_by_key[(first_scenario, treatment)]["delta_bytes_median"]
            for treatment in TREATMENTS
        },
        "recalled": {
            treatment: recalled[(first_scenario, treatment)] for treatment in TREATMENTS
        },
        "status": "measured",
    }
