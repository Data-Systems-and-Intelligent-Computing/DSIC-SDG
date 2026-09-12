from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h6c.pipeline import build_lineage
from kkciv_vintage.h9.pipeline import lineage_impact_index
from kkciv_vintage.h11.pipeline import (
    SUMMARY_COLUMNS,
    TREATMENTS,
    VALIDATION_COLUMNS,
    _manifest_entry,
    _read_csv,
    _sha256,
    _write_csv,
    execute_panel_treatments,
)


TABLE_COLUMNS = [
    "table_order",
    "scale",
    "treatment_id",
    "requests",
    "serving_state_successes",
    "historical_snapshot_successes",
    "historical_vintage_key_successes",
    "failures",
    "success_rate",
    "access_path",
]
PROFILE_COLUMNS = [
    "treatment_id",
    "failure_kind",
    "source_id",
    "domain",
    "geo_level",
    "failures",
    "material_failures",
    "duplicate_value_failures",
]
CASE_COLUMNS = [
    "case_order",
    "treatment_id",
    "failure_kind",
    "cell_id",
    "indicator_key",
    "observed_period",
    "geo_level",
    "geo_code",
    "unit",
    "lost_observation_id",
    "lost_source_id",
    "lost_release_date",
    "lost_value_lexeme",
    "served_observation_id",
    "served_source_id",
    "served_value_lexeme",
    "value_delta",
    "lost_source_artifact",
    "lost_source_record_id",
]
ACCESS_PATHS = {
    "B0": "observation_id in the current table",
    "B1": "observation_id in any state the table retains",
    "B2": "observation_id in the current table",
    "B3": "(cell_id, vintage_id) in the append-only store",
}
FAILURE_KIND = {
    "B0": "overwritten_by_later_vintage",
    "B2": "not_selected_by_trust_score",
}
SUPERSEDED = "serving_value_superseded"


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h13c.1"
        or contract.get("stage") != "H13"
        or contract.get("track") != "C"
    ):
        raise ValueError("unsupported H13C contract")
    procedure = contract["audit_procedure"]
    if procedure["required_steps"] != 10 or procedure["unclassified_failure_allowed"] is not False:
        raise ValueError("H13C must run the ten frozen audit steps and classify every failure")
    if procedure["identity_matching"] != "exact_observation_id":
        raise ValueError("H13C matches requests on the exact observation identity")
    if contract["scope"]["panel"]["requests"] != 6983 or contract["scope"]["fixture"]["requests"] != 38:
        raise ValueError("H13C audits the 38-request fixture and the 6983-request panel")
    if set(contract["access"]) != set(TREATMENTS):
        raise ValueError("H13C needs an access path per treatment")
    if contract["failure_classification"]["unclassified_allowed"] is not False:
        raise ValueError("H13C may not leave a failure unclassified")
    if contract["scope"]["synthetic_requests"] != "none; injected revisions are audited at H11 and stay there":
        raise ValueError("H13C audits published figures only")


def validate_procedure(steps: list[dict[str, str]], required: int) -> None:
    if len(steps) != required:
        raise ValueError(f"the frozen audit procedure must keep its {required} steps")
    orders = [int(row["step_order"]) for row in steps]
    if orders != list(range(1, required + 1)):
        raise ValueError("the frozen audit steps are no longer contiguous")
    for phase in ("preflight", "execution", "audit", "report"):
        if not any(row["phase"] == phase for row in steps):
            raise ValueError(f"the frozen audit procedure lost its {phase} phase")


def audit_panel(
    *,
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    scores: list[dict[str, str]],
    selection_contract_version: str,
    selection_run_id: str,
) -> dict[str, Any]:
    """Ask every treatment for every published figure of the panel, then explain the misses."""
    nodes, edges, paths, _ = build_lineage(vintages, observations)
    impact = lineage_impact_index(nodes, edges)
    executed = execute_panel_treatments(
        vintages=vintages,
        observations=observations,
        nodes=nodes,
        edges=edges,
        scores=scores,
        scoring_source_by_observation={},
        selection_contract_version=selection_contract_version,
        selection_run_id=selection_run_id,
    )
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    latest_by_cell: dict[str, dict[str, str]] = {}
    for row in observations:
        vintage = vintage_by_id[row["vintage_id"]]
        key = (vintage["vintage_date"], vintage["retrieved_at"], vintage["vintage_id"])
        current = latest_by_cell.get(row["cell_id"])
        if current is None or key > (
            vintage_by_id[current["vintage_id"]]["vintage_date"],
            vintage_by_id[current["vintage_id"]]["retrieved_at"],
            current["vintage_id"],
        ):
            latest_by_cell[row["cell_id"]] = row

    table: list[dict[str, str]] = []
    profile: list[dict[str, str]] = []
    cases: list[dict[str, str]] = []
    failures_by_treatment: dict[str, list[dict[str, str]]] = {}
    for order, treatment in enumerate(TREATMENTS, start=1):
        addressable = executed[treatment]["addressable"]
        serving = {row["cell_id"]: row for row in executed[treatment]["serving"]}
        serving_ids = {row["observation_id"] for row in serving.values()}
        lost = [row for row in observations if row["observation_id"] not in addressable]
        historical = len(addressable - serving_ids)
        table.append(
            {
                "table_order": str(order),
                "scale": "panel",
                "treatment_id": treatment,
                "requests": str(len(observations)),
                "serving_state_successes": str(len(addressable & serving_ids)),
                "historical_snapshot_successes": str(historical if treatment == "B1" else 0),
                "historical_vintage_key_successes": str(historical if treatment == "B3" else 0),
                "failures": str(len(lost)),
                "success_rate": f"{Decimal(len(addressable)) / Decimal(len(observations)):.4f}",
                "access_path": ACCESS_PATHS[treatment],
            }
        )
        if historical and treatment not in {"B1", "B3"}:
            raise ValueError(f"{treatment} answered from a state it does not keep")
        failures_by_treatment[treatment] = lost
        if not lost:
            continue

        kind = FAILURE_KIND[treatment]
        counts: Counter[tuple[str, str, str]] = Counter()
        material_counts: Counter[tuple[str, str, str]] = Counter()
        for row in lost:
            vintage = vintage_by_id[row["vintage_id"]]
            served = serving[row["cell_id"]]
            material = Decimal(row["value_decimal"]) != Decimal(served["value_decimal"])
            key = (vintage["source_id"], row["domain"], row["geo_level"])
            counts[key] += 1
            if material:
                material_counts[key] += 1
                cases.append(
                    {
                        "treatment_id": treatment,
                        "failure_kind": kind,
                        "cell_id": row["cell_id"],
                        "indicator_key": row["indicator_key"],
                        "observed_period": row["observed_period"],
                        "geo_level": row["geo_level"],
                        "geo_code": row["geo_code"],
                        "unit": row["unit"],
                        "lost_observation_id": row["observation_id"],
                        "lost_source_id": vintage["source_id"],
                        "lost_release_date": vintage["vintage_date"],
                        "lost_value_lexeme": row["value_lexeme"],
                        "served_observation_id": served["observation_id"],
                        "served_source_id": vintage_by_id[served["vintage_id"]]["source_id"],
                        "served_value_lexeme": served["value_lexeme"],
                        "value_delta": str(
                            Decimal(served["value_decimal"]) - Decimal(row["value_decimal"])
                        ),
                        "lost_source_artifact": row["source_artifact_path"],
                        "lost_source_record_id": row["source_record_id"],
                    }
                )
        for key in sorted(counts):
            profile.append(
                {
                    "treatment_id": treatment,
                    "failure_kind": kind,
                    "source_id": key[0],
                    "domain": key[1],
                    "geo_level": key[2],
                    "failures": str(counts[key]),
                    "material_failures": str(material_counts[key]),
                    "duplicate_value_failures": str(counts[key] - material_counts[key]),
                }
            )

    # A treatment can also serve a value the producer has already superseded. That is not a
    # failed request, so it is reported as its own kind rather than mixed into the recall.
    superseded: Counter[tuple[str, str, str]] = Counter()
    for treatment in TREATMENTS:
        serving = {row["cell_id"]: row for row in executed[treatment]["serving"]}
        for cell_id, row in sorted(serving.items()):
            latest = latest_by_cell[cell_id]
            if row["observation_id"] == latest["observation_id"]:
                continue
            if Decimal(row["value_decimal"]) == Decimal(latest["value_decimal"]):
                continue
            vintage = vintage_by_id[row["vintage_id"]]
            superseded[(treatment, row["domain"], row["geo_level"])] += 1
            cases.append(
                {
                    "treatment_id": treatment,
                    "failure_kind": SUPERSEDED,
                    "cell_id": cell_id,
                    "indicator_key": row["indicator_key"],
                    "observed_period": row["observed_period"],
                    "geo_level": row["geo_level"],
                    "geo_code": row["geo_code"],
                    "unit": row["unit"],
                    "lost_observation_id": latest["observation_id"],
                    "lost_source_id": vintage_by_id[latest["vintage_id"]]["source_id"],
                    "lost_release_date": vintage_by_id[latest["vintage_id"]]["vintage_date"],
                    "lost_value_lexeme": latest["value_lexeme"],
                    "served_observation_id": row["observation_id"],
                    "served_source_id": vintage["source_id"],
                    "served_value_lexeme": row["value_lexeme"],
                    "value_delta": str(
                        Decimal(row["value_decimal"]) - Decimal(latest["value_decimal"])
                    ),
                    "lost_source_artifact": latest["source_artifact_path"],
                    "lost_source_record_id": latest["source_record_id"],
                }
            )
    for (treatment, domain, geo_level), count in sorted(superseded.items()):
        profile.append(
            {
                "treatment_id": treatment,
                "failure_kind": SUPERSEDED,
                "source_id": "",
                "domain": domain,
                "geo_level": geo_level,
                "failures": str(count),
                "material_failures": str(count),
                "duplicate_value_failures": "0",
            }
        )

    ordered_cases = sorted(
        cases,
        key=lambda row: (
            TREATMENTS.index(row["treatment_id"]),
            row["failure_kind"],
            row["indicator_key"],
            row["observed_period"],
            row["geo_code"],
        ),
    )
    for index, row in enumerate(ordered_cases, start=1):
        row["case_order"] = str(index)

    resolved = sum(1 for row in observations if row["observation_id"] in impact)
    return {
        "table": table,
        "profile": profile,
        "cases": ordered_cases,
        "failures": failures_by_treatment,
        "lineage": {
            "nodes": len(nodes),
            "edges": len(edges),
            "paths": len(paths),
            "resolved_requests": resolved,
            "completeness": f"{Decimal(resolved) / Decimal(len(observations)):.4f}",
        },
    }


def cross_check_physical(
    *, table: list[dict[str, str]], recall_rows: list[dict[str, str]], scenarios: list[dict[str, str]]
) -> list[dict[str, str]]:
    """The derived audit must agree with what the physical sweep returned."""
    derived = {row["treatment_id"]: int(row["requests"]) - int(row["failures"]) for row in table}
    revised = {row["scenario_id"]: int(row["cells_revised"]) for row in scenarios}
    checked: list[dict[str, str]] = []
    for row in recall_rows:
        if row["request_kind"] != "official":
            continue
        treatment = row["treatment_id"]
        expected = derived[treatment]
        if treatment in {"B0", "B2"}:
            expected -= revised[row["scenario_id"]]
        if int(row["addressable"]) != expected:
            raise ValueError(
                f"the audit derives {expected} official recalls for {treatment} at {row['scenario_id']} "
                f"while the sweep measured {row['addressable']}"
            )
        checked.append(
            {
                "scenario_id": row["scenario_id"],
                "treatment_id": treatment,
                "measured": row["addressable"],
                "derived": str(expected),
            }
        )
    return checked


def build_validation(
    *,
    contract: dict[str, Any],
    steps: list[dict[str, str]],
    table: list[dict[str, str]],
    profile: list[dict[str, str]],
    cases: list[dict[str, str]],
    failures: dict[str, list[dict[str, str]]],
    lineage: dict[str, Any],
    cross_checks: list[dict[str, str]],
    fixture_table: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(invariant: str, ok: bool, checked: int, detail: str) -> None:
        rows.append(
            {
                "invariant": invariant,
                "status": "pass" if ok else "fail",
                "checked_rows": str(checked),
                "detail": detail,
            }
        )

    add(
        "the ten audit steps frozen at H8C are unchanged",
        len(steps) == contract["audit_procedure"]["required_steps"],
        len(steps),
        ";".join(row["step_id"] for row in steps),
    )
    panel = [row for row in table if row["scale"] == "panel"]
    add(
        "all four treatments answer exactly the same request set",
        len({row["requests"] for row in panel}) == 1 and len(panel) == len(TREATMENTS),
        len(panel),
        f"{panel[0]['requests']} published figures asked of every treatment",
    )
    classified = sum(int(row["failures"]) for row in profile if row["failure_kind"] != SUPERSEDED)
    add(
        "every failure is classified",
        classified == sum(len(rows_) for rows_ in failures.values()),
        classified,
        f"{classified} failures over {len({row['failure_kind'] for row in profile})} kinds",
    )
    add(
        "every request resolves to its source record through the lineage",
        lineage["completeness"] == "1.0000",
        lineage["resolved_requests"],
        f"{lineage['nodes']} nodes, {lineage['edges']} edges, completeness {lineage['completeness']}",
    )
    add(
        "the derived recall agrees with the recall the sweep measured",
        bool(cross_checks),
        len(cross_checks),
        f"{len(cross_checks)} scenario-treatment pairs checked against results/processed/h11-recall.csv",
    )
    keeping = [row for row in panel if row["treatment_id"] in {"B1", "B3"}]
    add(
        "B1 and B3 reproduce every published figure",
        all(row["failures"] == "0" and row["success_rate"] == "1.0000" for row in keeping),
        len(keeping),
        ";".join(f"{row['treatment_id']}={row['success_rate']}" for row in keeping),
    )
    add(
        "the fixture audit of H9C is carried forward unchanged",
        len(fixture_table) == len(TREATMENTS),
        len(fixture_table),
        ";".join(f"{row['treatment_id']}={row['success_rate']}" for row in fixture_table),
    )
    material = sum(1 for row in cases if row["failure_kind"] != SUPERSEDED)
    add(
        "every material failure names the lost figure and its source record",
        all(row["lost_source_artifact"] and row["lost_source_record_id"] for row in cases),
        material,
        f"{material} published values that can no longer be produced, each with its artifact and locator",
    )
    return rows


def build_summary(
    *,
    table: list[dict[str, str]],
    profile: list[dict[str, str]],
    cases: list[dict[str, str]],
    lineage: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in table:
        if row["scale"] != "panel":
            continue
        rows.append(
            {
                "metric": f"{row['treatment_id'].lower()}_panel_recall",
                "value": row["success_rate"],
                "unit": "ratio",
                "interpretation": (
                    f"{int(row['requests']) - int(row['failures'])} of {row['requests']} published figures, "
                    f"answered through {row['access_path']}"
                ),
            }
        )
    for treatment in TREATMENTS:
        selected = [row for row in profile if row["treatment_id"] == treatment and row["failure_kind"] != SUPERSEDED]
        if not selected:
            continue
        rows.append(
            {
                "metric": f"{treatment.lower()}_material_failures",
                "value": str(sum(int(row["material_failures"]) for row in selected)),
                "unit": "figures",
                "interpretation": (
                    f"{sum(int(row['failures']) for row in selected)} figures cannot be reproduced, and this "
                    "many of them carry a value the treatment no longer serves anywhere"
                ),
            }
        )
    superseded = [row for row in cases if row["failure_kind"] == SUPERSEDED]
    for treatment in sorted({row["treatment_id"] for row in superseded}):
        rows.append(
            {
                "metric": f"{treatment.lower()}_superseded_serving_cells",
                "value": str(sum(1 for row in superseded if row["treatment_id"] == treatment)),
                "unit": "cells",
                "interpretation": "cells served with a value the producer has already replaced with a different one",
            }
        )
    rows.append(
        {
            "metric": "lineage_completeness",
            "value": lineage["completeness"],
            "unit": "ratio",
            "interpretation": (
                f"{lineage['resolved_requests']} requests resolved to a source record over "
                f"{lineage['nodes']} nodes and {lineage['edges']} edges"
            ),
        }
    )
    return rows


def run_h13c(
    *,
    contract_path: Path,
    steps_path: Path,
    panel_manifest_path: Path,
    h9c_table_path: Path,
    recall_path: Path,
    scores_path: Path,
    b2_contract_path: Path,
    table_output: Path,
    profile_output: Path,
    cases_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    steps = _read_csv(steps_path)
    validate_procedure(steps, contract["audit_procedure"]["required_steps"])

    payload = json.loads(panel_manifest_path.read_text(encoding="utf-8"))
    if payload.get("stage") != "H11" or payload.get("payload_status") != "prepared":
        raise ValueError("H13C needs the prepared H11 panel payload")
    outputs = {}
    for item in payload["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested payload output {path}")
        outputs[path.name] = path
    observations = _read_csv(outputs["h11-panel-observations.csv"])
    vintages = _read_csv(outputs["h11-panel-vintages.csv"])
    scenarios = _read_csv(outputs["h11-sweep-scenarios.csv"])
    if len(observations) != contract["scope"]["panel"]["requests"]:
        raise ValueError("the panel no longer holds the number of published figures the contract states")

    b2_contract = json.loads(b2_contract_path.read_text(encoding="utf-8"))
    audited = audit_panel(
        vintages=vintages,
        observations=observations,
        scores=_read_csv(scores_path),
        selection_contract_version=b2_contract["contract_version"],
        selection_run_id="h13c-" + _sha256(contract_path)[:20],
    )
    cross_checks = cross_check_physical(
        table=audited["table"], recall_rows=_read_csv(recall_path), scenarios=scenarios
    )

    fixture_table = _read_csv(h9c_table_path)
    table = [
        *[
            {
                "table_order": row["table_order"],
                "scale": "fixture",
                "treatment_id": row["treatment_id"],
                "requests": row["requests"],
                "serving_state_successes": row["serving_state_successes"],
                "historical_snapshot_successes": row["historical_snapshot_successes"],
                "historical_vintage_key_successes": row["historical_vintage_key_successes"],
                "failures": row["failures"],
                "success_rate": row["success_rate"],
                "access_path": ACCESS_PATHS[row["treatment_id"]],
            }
            for row in fixture_table
        ],
        *audited["table"],
    ]
    validation_rows = build_validation(
        contract=contract,
        steps=steps,
        table=table,
        profile=audited["profile"],
        cases=audited["cases"],
        failures=audited["failures"],
        lineage=audited["lineage"],
        cross_checks=cross_checks,
        fixture_table=fixture_table,
    )
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["invariant"] for row in validation_rows if row["status"] != "pass"]
        raise ValueError(f"H13C invariants failed: {failed}")
    summary_rows = build_summary(
        table=table, profile=audited["profile"], cases=audited["cases"], lineage=audited["lineage"]
    )

    written = []
    for path, columns, rows in (
        (table_output, TABLE_COLUMNS, table),
        (profile_output, PROFILE_COLUMNS, audited["profile"]),
        (cases_output, CASE_COLUMNS, audited["cases"]),
        (validation_output, VALIDATION_COLUMNS, validation_rows),
        (summary_output, SUMMARY_COLUMNS, summary_rows),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    panel = {row["treatment_id"]: row for row in table if row["scale"] == "panel"}
    material = {
        treatment: sum(
            int(row["material_failures"])
            for row in audited["profile"]
            if row["treatment_id"] == treatment and row["failure_kind"] != SUPERSEDED
        )
        for treatment in TREATMENTS
    }
    superseded = {
        treatment: sum(
            1
            for row in audited["cases"]
            if row["treatment_id"] == treatment and row["failure_kind"] == SUPERSEDED
        )
        for treatment in TREATMENTS
    }
    manifest = {
        "stage": "H13",
        "track": "C",
        "contract_version": contract["contract_version"],
        "audit_status": "validated",
        "panel": {
            "requests": len(observations),
            "cells": len({row["cell_id"] for row in observations}),
            **audited["lineage"],
        },
        "recall": {treatment: panel[treatment]["success_rate"] for treatment in TREATMENTS},
        "material_failures": material,
        "superseded_serving_cells": superseded,
        "cross_checks": len(cross_checks),
        "inputs": [
            _manifest_entry(path)
            for path in (
                contract_path,
                steps_path,
                panel_manifest_path,
                h9c_table_path,
                recall_path,
                scores_path,
                b2_contract_path,
            )
        ],
        "outputs": written,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "requests": len(observations),
        "recall": {treatment: panel[treatment]["success_rate"] for treatment in TREATMENTS},
        "failures": {treatment: panel[treatment]["failures"] for treatment in TREATMENTS},
        "material_failures": material,
        "superseded_serving_cells": superseded,
        "cross_checks": len(cross_checks),
        "lineage_completeness": audited["lineage"]["completeness"],
        "cases": len(audited["cases"]),
        "status": "validated",
    }
