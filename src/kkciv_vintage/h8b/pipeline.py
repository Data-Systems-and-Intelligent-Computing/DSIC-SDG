from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


PLAN_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "seed",
    "selection_count",
    "base_cell_count",
    "selection_fraction",
    "selected_rank_min",
    "selected_rank_max",
    "synthetic_vintage_id",
    "workload_sha256",
    "profile_status",
    "nested_from_previous",
]
INJECTION_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "seed",
    "selection_rank",
    "base_observation_id",
    "base_vintage_id",
    "revised_source_id",
    "cell_id",
    "domain",
    "indicator_key",
    "series_key",
    "observed_period",
    "period_granularity",
    "geo_level",
    "geo_code",
    "geo_name",
    "unit",
    "before_value_decimal",
    "before_value_lexeme",
    "published_decimal_places",
    "delta_decimal",
    "after_value_decimal",
    "after_value_lexeme",
    "synthetic_vintage_id",
    "synthetic_observation_id",
    "synthetic_source_id",
    "provenance_class",
    "mutation_rule",
]
ROUTE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "treatment_id",
    "canonical_input_path",
    "scenario_filter",
    "workload_sha256",
    "input_rows",
    "execution_status",
]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]
SUMMARY_COLUMNS = ["metric", "value", "unit", "interpretation"]
PROTECTED_DIMENSIONS = [
    "cell_id",
    "domain",
    "indicator_key",
    "series_key",
    "observed_period",
    "period_granularity",
    "geo_level",
    "geo_code",
    "geo_name",
    "unit",
]
TREATMENTS = ["B0", "B1", "B2", "B3"]
REQUIRED_HUMAN_DECISIONS = {
    "h8b_base_state": ("injection_base", "use_latest_vintage_as_canonical_base"),
    "h8b_mutation_unit": ("mutation_rule", "change_exactly_one_published_unit"),
    "h8b_main_sweep_source": ("main_sweep", "exactly_one_revised_source_per_run"),
}
TEN_PLACES = Decimal("0.0000000001")


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


def _short_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _payload_hash(rows: list[dict[str, str]]) -> str:
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
        contract.get("contract_version") != "h8b.2"
        or contract.get("stage") != "H8"
        or contract.get("track") != "B"
    ):
        raise ValueError("unsupported H8B harness contract")
    profile = contract["scenario_profile"]
    if profile["status"] != "validation_only" or profile["final_experiment_freeze"] is not False:
        raise ValueError("H8B validation profile must not claim the final experiment freeze")
    decisions = contract["human_decisions"]
    if decisions != {
        "registry": "config/h8b/human_decisions.csv",
        "approved_at": "2026-09-10",
        "latest_vintage_as_canonical_base": True,
        "one_published_unit_mutation": True,
        "main_sweep_exactly_one_revised_source_per_run": True,
        "validation_profile_may_mix_revised_sources": True,
    }:
        raise ValueError("H8B human decisions do not match the approved protocol")
    selection = contract["selection"]
    if selection != {
        "algorithm": "sort by sha256(seed + unit-separator + cell_id), then cell_id; take the first selection_count cells",
        "nested_prefixes": True,
        "seed_source": "explicit scenario config",
        "random_runtime_state": False,
    }:
        raise ValueError("H8B cell selection must be deterministic and nested")
    mutation = contract["mutation"]
    if mutation["storage_type"] != "DECIMAL(38,10)" or mutation["must_change_numeric_value"] is not True:
        raise ValueError("H8B mutation must preserve exact decimal values and change every target")
    if mutation["protected_dimensions"] != PROTECTED_DIMENSIONS:
        raise ValueError("H8B protected cell dimensions do not match the implementation")
    provenance = contract["synthetic_provenance"]
    if (
        provenance["source_id"] != "synthetic_revision_harness"
        or provenance["provenance_class"] != "synthetic_not_official"
        or provenance["revised_source_id"]
        != "inherit the official source_id associated with the base vintage"
        or provenance["b2_score_policy"]
        != "look up the frozen score of revised_source_id; never score synthetic_source_id"
        or provenance["must_not_masquerade_as_bps"] is not True
    ):
        raise ValueError("H8B synthetic provenance must never masquerade as BPS")
    routing = contract["routing"]
    if (
        routing["treatments"] != TREATMENTS
        or routing["treatment_specific_mutation"] is not False
        or routing["execution_status_at_H8"] != "prepared_not_run"
    ):
        raise ValueError("H8B must route one unchanged payload to all four treatments")
    boundary = contract["measurement_boundary"]
    if boundary["timing"] != "not_measured" or boundary["storage"] != "not_measured":
        raise ValueError("H8B must not claim timing or storage measurements")


def validate_human_decisions(rows: list[dict[str, str]]) -> None:
    if len(rows) != len(REQUIRED_HUMAN_DECISIONS):
        raise ValueError("H8B requires exactly three human decisions")
    by_id = {row["decision_id"]: row for row in rows}
    if set(by_id) != set(REQUIRED_HUMAN_DECISIONS):
        raise ValueError("H8B human decision IDs are incomplete")
    for decision_id, (scope, decision) in REQUIRED_HUMAN_DECISIONS.items():
        row = by_id[decision_id]
        if (
            row["decided_at"] != "2026-09-10"
            or row["decided_by"] != "human_reviewer"
            or row["status"] != "approved"
            or row["scope"] != scope
            or row["decision"] != decision
            or not row["rationale"]
        ):
            raise ValueError(f"H8B human decision {decision_id} is not approved as recorded")


def _manifested_b0_state(manifest_path: Path) -> tuple[Path, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("stage") != "H7"
        or manifest.get("treatment_id") != "B0"
        or manifest.get("implementation_status") != "implemented"
    ):
        raise ValueError("H8B requires the implemented B0 latest-vintage state")
    for item in manifest["outputs"]:
        if Path(item["path"]).name != "h7-b0-final-state.csv":
            continue
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError("invalid manifested B0 final state")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError("B0 final-state row count does not match its manifest")
        return path, item
    raise ValueError("B0 manifest is missing h7-b0-final-state.csv")


def _manifested_h6_vintages(manifest_path: Path) -> tuple[Path, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "H6" or manifest.get("schema_status") != "validated":
        raise ValueError("H8B requires the validated H6 vintage dimension")
    for item in manifest["outputs"]:
        if Path(item["path"]).name != "h6-release-vintages.csv":
            continue
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError("invalid manifested H6 vintage dimension")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError("H6 vintage row count does not match its manifest")
        return path, item
    raise ValueError("H6 manifest is missing h6-release-vintages.csv")


def _validate_scenarios(
    scenarios: list[dict[str, str]], *, base_cell_count: int, required_sizes: list[int]
) -> tuple[list[dict[str, str]], str]:
    if not scenarios:
        raise ValueError("H8B requires at least one injection scenario")
    ordered = sorted(scenarios, key=lambda row: int(row["scenario_order"]))
    orders = [int(row["scenario_order"]) for row in ordered]
    if orders != list(range(1, len(ordered) + 1)):
        raise ValueError("H8B scenario_order must be contiguous from one")
    if len({row["scenario_id"] for row in ordered}) != len(ordered):
        raise ValueError("H8B scenario_id values must be unique")
    seeds = {row["seed"] for row in ordered}
    if len(seeds) != 1 or not next(iter(seeds)).isdigit():
        raise ValueError("H8B validation scenarios must share one explicit numeric seed")
    sizes = [int(row["selection_count"]) for row in ordered]
    if sizes != sorted(set(sizes)) or sizes != required_sizes:
        raise ValueError("H8B scenario sizes do not match the ordered validation profile")
    if sizes[0] != 1 or sizes[-1] != base_cell_count:
        raise ValueError("H8B validation profile must span one cell through the complete fixture")
    if any(row["profile_status"] != "validation_only" for row in ordered):
        raise ValueError("H8B scenarios must remain labeled validation_only")
    return ordered, next(iter(seeds))


def _format_storage(value: Decimal) -> str:
    return f"{value.quantize(TEN_PLACES):.10f}"


def _format_lexeme(value: Decimal, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    return f"{value.quantize(quantum):.{places}f}"


def build_injected_workloads(
    *,
    base_rows: list[dict[str, str]],
    source_by_vintage: dict[str, str],
    scenarios: list[dict[str, str]],
    required_sizes: list[int],
    canonical_input_path: str,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, int | str],
]:
    if not base_rows or len({row["cell_id"] for row in base_rows}) != len(base_rows):
        raise ValueError("H8B base state must contain exactly one row per cell_id")
    if unknown := {row["vintage_id"] for row in base_rows} - source_by_vintage.keys():
        raise ValueError(f"H8B base state references unknown vintages {sorted(unknown)}")
    ordered_scenarios, seed = _validate_scenarios(
        scenarios, base_cell_count=len(base_rows), required_sizes=required_sizes
    )
    ranked = sorted(
        base_rows,
        key=lambda row: (
            hashlib.sha256(f"{seed}\x1f{row['cell_id']}".encode("utf-8")).hexdigest(),
            row["cell_id"],
        ),
    )

    plans: list[dict[str, str]] = []
    injections: list[dict[str, str]] = []
    routes: list[dict[str, str]] = []
    previous_cells: set[str] = set()
    for scenario in ordered_scenarios:
        count = int(scenario["selection_count"])
        selected = ranked[:count]
        synthetic_vintage_id = _short_hash(
            f"H8B|vintage|{scenario['scenario_id']}|{seed}|{count}"
        )
        scenario_rows: list[dict[str, str]] = []
        for rank, base in enumerate(selected, start=1):
            places = int(base["published_decimal_places"])
            if places < 0 or places > 10:
                raise ValueError("H8B published_decimal_places must be between zero and ten")
            before = Decimal(base["value_decimal"])
            step = Decimal(1).scaleb(-places)
            delta = -step if base["unit"].casefold() == "percent" and before + step > 100 else step
            after = before + delta
            synthetic_observation_id = _short_hash(
                f"H8B|observation|{scenario['scenario_id']}|{base['cell_id']}|{_format_storage(after)}"
            )
            row = {
                "scenario_order": scenario["scenario_order"],
                "scenario_id": scenario["scenario_id"],
                "seed": seed,
                "selection_rank": str(rank),
                "base_observation_id": base["observation_id"],
                "base_vintage_id": base["vintage_id"],
                "revised_source_id": source_by_vintage[base["vintage_id"]],
                **{column: base[column] for column in PROTECTED_DIMENSIONS},
                "before_value_decimal": _format_storage(before),
                "before_value_lexeme": base["value_lexeme"],
                "published_decimal_places": str(places),
                "delta_decimal": _format_storage(delta),
                "after_value_decimal": _format_storage(after),
                "after_value_lexeme": _format_lexeme(after, places),
                "synthetic_vintage_id": synthetic_vintage_id,
                "synthetic_observation_id": synthetic_observation_id,
                "synthetic_source_id": "synthetic_revision_harness",
                "provenance_class": "synthetic_not_official",
                "mutation_rule": "one_published_unit",
            }
            if Decimal(row["before_value_decimal"]) == Decimal(row["after_value_decimal"]):
                raise ValueError("H8B mutation did not change a selected value")
            scenario_rows.append(row)
        injections.extend(scenario_rows)
        workload_sha256 = _payload_hash(scenario_rows)
        selected_cells = {row["cell_id"] for row in scenario_rows}
        if not previous_cells.issubset(selected_cells):
            raise ValueError("H8B scenarios are not nested prefixes")
        plans.append(
            {
                "scenario_order": scenario["scenario_order"],
                "scenario_id": scenario["scenario_id"],
                "seed": seed,
                "selection_count": str(count),
                "base_cell_count": str(len(base_rows)),
                "selection_fraction": f"{Decimal(count) / Decimal(len(base_rows)):.6f}",
                "selected_rank_min": "1",
                "selected_rank_max": str(count),
                "synthetic_vintage_id": synthetic_vintage_id,
                "workload_sha256": workload_sha256,
                "profile_status": scenario["profile_status"],
                "nested_from_previous": "yes" if previous_cells else "not_applicable",
            }
        )
        for treatment_id in TREATMENTS:
            routes.append(
                {
                    "scenario_order": scenario["scenario_order"],
                    "scenario_id": scenario["scenario_id"],
                    "treatment_id": treatment_id,
                    "canonical_input_path": canonical_input_path,
                    "scenario_filter": f"scenario_id={scenario['scenario_id']}",
                    "workload_sha256": workload_sha256,
                    "input_rows": str(count),
                    "execution_status": "prepared_not_run",
                }
            )
        previous_cells = selected_cells

    route_mismatches = 0
    for plan in plans:
        scenario_routes = [row for row in routes if row["scenario_id"] == plan["scenario_id"]]
        if (
            len(scenario_routes) != len(TREATMENTS)
            or {row["treatment_id"] for row in scenario_routes} != set(TREATMENTS)
            or {row["workload_sha256"] for row in scenario_routes} != {plan["workload_sha256"]}
            or {row["input_rows"] for row in scenario_routes} != {plan["selection_count"]}
        ):
            route_mismatches += 1
    metrics: dict[str, int | str] = {
        "base_cells": len(base_rows),
        "scenario_count": len(plans),
        "scenario_sizes": "-".join(row["selection_count"] for row in plans),
        "injected_rows": len(injections),
        "treatment_count": len(TREATMENTS),
        "route_rows": len(routes),
        "route_mismatches": route_mismatches,
    }
    if route_mismatches:
        raise ValueError("H8B treatment routes do not share the same canonical workload")
    return plans, injections, routes, metrics


def run_h8b(
    *,
    contract_path: Path,
    scenario_path: Path,
    human_decisions_path: Path,
    b0_manifest_path: Path,
    h6_manifest_path: Path,
    plan_output: Path,
    injections_output: Path,
    routes_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    human_decisions = _read_csv(human_decisions_path)
    validate_human_decisions(human_decisions)
    base_path, base_item = _manifested_b0_state(b0_manifest_path)
    vintage_path, vintage_item = _manifested_h6_vintages(h6_manifest_path)
    base_rows = _read_csv(base_path)
    vintages = _read_csv(vintage_path)
    source_by_vintage = {row["vintage_id"]: row["source_id"] for row in vintages}
    scenarios = _read_csv(scenario_path)
    plans, injections, routes, metrics = build_injected_workloads(
        base_rows=base_rows,
        source_by_vintage=source_by_vintage,
        scenarios=scenarios,
        required_sizes=contract["scenario_profile"]["required_fixture_sizes"],
        canonical_input_path=str(injections_output),
    )
    validations = [
        {"invariant": "unique_base_cells", "status": "passed", "checked_rows": str(metrics["base_cells"]), "detail": "B0 contributes one latest observation per stable cell"},
        {"invariant": "explicit_validation_profile", "status": "passed", "checked_rows": str(metrics["scenario_count"]), "detail": f"ordered sizes {metrics['scenario_sizes']} are labeled validation_only"},
        {"invariant": "human_method_decisions", "status": "passed", "checked_rows": str(len(human_decisions)), "detail": "canonical base, mutation unit, and single-source main sweep were approved on 2026-09-10"},
        {"invariant": "deterministic_nested_selection", "status": "passed", "checked_rows": str(metrics["injected_rows"]), "detail": "one seeded SHA-256 ranking supplies every nested prefix"},
        {"invariant": "exact_value_mutation", "status": "passed", "checked_rows": str(metrics["injected_rows"]), "detail": "every target changes by one published decimal unit"},
        {"invariant": "protected_cell_dimensions", "status": "passed", "checked_rows": str(metrics["injected_rows"]), "detail": "the synthetic batch identifies cells without changing their dimensions"},
        {"invariant": "explicit_synthetic_provenance", "status": "passed", "checked_rows": str(metrics["injected_rows"]), "detail": "no injected record is labeled as an official BPS release"},
        {"invariant": "revised_source_mapping", "status": "passed", "checked_rows": str(metrics["injected_rows"]), "detail": "every synthetic record names the official source whose frozen B2 score an adapter must use"},
        {"invariant": "identical_four_treatment_routes", "status": "passed", "checked_rows": str(metrics["route_rows"]), "detail": "B0-B3 share one per-scenario canonical payload checksum"},
        {"invariant": "no_measurement_claim", "status": "passed", "checked_rows": "0", "detail": "timing and physical storage are not measured at H8"},
    ]
    summary = [
        {"metric": "base_cells", "value": str(metrics["base_cells"]), "unit": "cells", "interpretation": "manifested B0 latest-vintage validation fixture"},
        {"metric": "validation_scenarios", "value": str(metrics["scenario_count"]), "unit": "scenarios", "interpretation": "not the final H10 experiment freeze"},
        {"metric": "approved_human_decisions", "value": str(len(human_decisions)), "unit": "decisions", "interpretation": "base state, mutation unit, and main-sweep source scope"},
        {"metric": "scenario_sizes", "value": str(metrics["scenario_sizes"]), "unit": "cells", "interpretation": "nested deterministic validation prefixes"},
        {"metric": "injected_revision_rows", "value": str(metrics["injected_rows"]), "unit": "rows", "interpretation": "sum across independent validation scenarios"},
        {"metric": "target_treatments", "value": str(metrics["treatment_count"]), "unit": "treatments", "interpretation": "B0, B1, B2, and planned B3"},
        {"metric": "prepared_routes", "value": str(metrics["route_rows"]), "unit": "routes", "interpretation": "one route per scenario and treatment"},
        {"metric": "route_payload_mismatches", "value": str(metrics["route_mismatches"]), "unit": "scenarios", "interpretation": "must be zero before treatment execution"},
        {"metric": "timed_runs", "value": "0", "unit": "runs", "interpretation": "small execution starts at H9"},
        {"metric": "physical_storage_measurements", "value": "0", "unit": "measurements", "interpretation": "measurement starts after the experiment freeze"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (plan_output, PLAN_COLUMNS, plans),
        (injections_output, INJECTION_COLUMNS, injections),
        (routes_output, ROUTE_COLUMNS, routes),
        (validation_output, VALIDATION_COLUMNS, validations),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H8",
        "track": "B",
        "harness_status": "validation_ready",
        "contract_version": contract["contract_version"],
        "profile": {
            "status": "validation_only",
            "final_experiment_freeze": False,
            **metrics,
        },
        "human_decisions": {
            "approved": len(human_decisions),
            "approved_at": "2026-09-10",
            "main_sweep_source_scope": "exactly_one_revised_source_per_run",
            "validation_profile_may_mix_revised_sources": True,
        },
        "measurement": contract["measurement_boundary"],
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(scenario_path), "rows": len(scenarios), "sha256": _sha256(scenario_path)},
            {"path": str(human_decisions_path), "rows": len(human_decisions), "sha256": _sha256(human_decisions_path)},
            {"path": str(b0_manifest_path), "sha256": _sha256(b0_manifest_path)},
            {"path": str(base_path), "rows": base_item["rows"], "sha256": base_item["sha256"]},
            {"path": str(h6_manifest_path), "sha256": _sha256(h6_manifest_path)},
            {"path": str(vintage_path), "rows": vintage_item["rows"], "sha256": vintage_item["sha256"]},
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        **metrics,
        "approved_human_decisions": len(human_decisions),
        "status": manifest["harness_status"],
    }
