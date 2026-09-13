from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h11.pipeline import (
    SUMMARY_COLUMNS,
    TREATMENTS,
    VALIDATION_COLUMNS,
    _manifest_entry,
    _read_csv,
    _write_csv,
)


DECOMPOSITION_COLUMNS = [
    "treatment_id",
    "measure",
    "points",
    "sweep_sizes",
    "intercept",
    "slope_per_revised_cell",
    "observed_min",
    "observed_max",
    "write_share",
    "maintenance_share",
    "status",
]
CONDITION_COLUMNS = [
    "comparison",
    "measure",
    "measured_direction",
    "measured_crossing",
    "intercept_gap",
    "slope_gap",
    "projected_crossing_cells",
    "projection_status",
    "condition_for_a_crossing",
]
REPRODUCIBILITY_COST_COLUMNS = [
    "treatment_id",
    "panel_recall",
    "panel_failures",
    "material_failures",
    "superseded_serving_cells",
    "seconds_per_revision",
    "maintenance_share",
    "bytes_per_revision_intercept",
    "bytes_per_revised_cell",
    "bytes_read_per_revision",
    "real_releases_seconds",
    "verdict",
]
FAILURE_SYNTHESIS_COLUMNS = [
    "failure_kind",
    "treatments_affected",
    "figures_affected",
    "material_figures",
    "consequence",
    "treatments_free_of_it",
    "price_of_avoiding_it",
]
SUPERSEDED = "serving_value_superseded"


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h14c.1"
        or contract.get("stage") != "H14"
        or contract.get("track") != "C"
    ):
        raise ValueError("unsupported H14C contract")
    decomposition = contract["decomposition"]
    if decomposition["status"] != "descriptive" or not decomposition["not_claimed"]:
        raise ValueError("the H14C decomposition is descriptive and must say so")
    projection = contract["breakeven"]["projection"]
    if projection["must_be_labelled"] != "outside_measured_range":
        raise ValueError("a projected crossing must be labelled as outside the measured range")
    if "may never be reported as a break-even point" not in projection["never"]:
        raise ValueError("H14C may never turn a projection into a break-even point")
    if contract["synthesis"]["recall_source_is_authoritative"] != (
        "recall figures are copied from the H13C audit, never recomputed here"
    ):
        raise ValueError("H14C must copy the recall figures from the audit that measured them")


def fit_line(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Ordinary least squares over the measured points. Descriptive, not inferential."""
    if len(points) < 2:
        raise ValueError("a line needs at least two measured points")
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator == 0:
        raise ValueError("the sweep sizes must differ for a slope to exist")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator
    return slope, mean_y - slope * mean_x


def decompose(cost_rows: list[dict[str, str]], measures: list[str]) -> list[dict[str, str]]:
    sizes = sorted({int(row["cells_revised"]) for row in cost_rows})
    measured = [
        treatment
        for treatment in TREATMENTS
        if any(row["treatment_id"] == treatment for row in cost_rows)
    ]
    rows: list[dict[str, str]] = []
    for treatment in measured:
        selected = sorted(
            (row for row in cost_rows if row["treatment_id"] == treatment),
            key=lambda row: int(row["cells_revised"]),
        )
        write = sum(float(row["write_seconds_median"]) for row in selected) / len(selected)
        maintenance = sum(float(row["maintenance_seconds_median"]) for row in selected) / len(selected)
        total = write + maintenance
        for measure in measures:
            points = [(float(row["cells_revised"]), float(row[measure])) for row in selected]
            slope, intercept = fit_line(points)
            values = [value for _, value in points]
            rows.append(
                {
                    "treatment_id": treatment,
                    "measure": measure,
                    "points": str(len(points)),
                    "sweep_sizes": "-".join(str(size) for size in sizes),
                    "intercept": f"{intercept:.4f}",
                    "slope_per_revised_cell": f"{slope:.4f}",
                    "observed_min": f"{min(values):.4f}",
                    "observed_max": f"{max(values):.4f}",
                    "write_share": f"{write / total:.4f}" if total else "",
                    "maintenance_share": f"{maintenance / total:.4f}" if total else "",
                    "status": "descriptive",
                }
            )
    return rows


def trend_is_resolved(
    cost_rows: list[dict[str, str]], *, treatment: str, measure: str
) -> bool:
    """A trend counts as resolved only when the measured ranges at the ends do not overlap.

    Fitting a line through six noisy points always yields a slope; that slope means nothing
    unless the smallest and the largest sweep point are actually distinguishable.
    """
    selected = sorted(
        (row for row in cost_rows if row["treatment_id"] == treatment),
        key=lambda row: int(row["cells_revised"]),
    )
    prefix = "write_seconds" if measure.startswith("total_seconds") else "delta_bytes"
    if measure.startswith("total_seconds"):
        # The reported range of the total is the range of its write phase plus maintenance.
        def bounds(row: dict[str, str]) -> tuple[float, float]:
            maintenance = float(row["maintenance_seconds_median"])
            return (
                float(row["write_seconds_min"]) + maintenance,
                float(row["write_seconds_max"]) + maintenance,
            )
    else:
        def bounds(row: dict[str, str]) -> tuple[float, float]:
            return float(row[f"{prefix}_min"]), float(row[f"{prefix}_max"])

    low_first, high_first = bounds(selected[0])
    low_last, high_last = bounds(selected[-1])
    disjoint_ends = high_first < low_last or high_last < low_first
    # Disjoint ends alone can come from one long repetition, so the medians must also move
    # in one direction across every swept size before a trend counts as resolved.
    medians = [float(row[measure]) for row in selected]
    monotone = all(
        later >= earlier for earlier, later in zip(medians, medians[1:])
    ) or all(later <= earlier for earlier, later in zip(medians, medians[1:]))
    return disjoint_ends and monotone


def project_conditions(
    *,
    decomposition: list[dict[str, str]],
    measured: list[dict[str, str]],
    cost_rows: list[dict[str, str]],
    largest_measured_size: int,
    panel_cells: int,
) -> list[dict[str, str]]:
    """Say how far a crossing would be if the measured line kept going, and never call it one."""
    by_key = {(row["treatment_id"], row["measure"]): row for row in decomposition}
    rows: list[dict[str, str]] = []
    for row in measured:
        incremental = row["incremental_treatment"]
        comparator = row["comparator_treatment"]
        measure = row["measure"]
        left = by_key[(incremental, measure)]
        right = by_key[(comparator, measure)]
        intercept_gap = Decimal(left["intercept"]) - Decimal(right["intercept"])
        slope_gap = Decimal(left["slope_per_revised_cell"]) - Decimal(right["slope_per_revised_cell"])
        projected = ""
        resolved = trend_is_resolved(
            cost_rows, treatment=incremental, measure=measure
        ) or trend_is_resolved(cost_rows, treatment=comparator, measure=measure)
        if not resolved:
            status = "flat_within_the_measured_ranges"
        elif slope_gap != 0:
            crossing = -intercept_gap / slope_gap
            if crossing > 0:
                projected = f"{crossing:.0f}"
                status = (
                    "outside_measured_range"
                    if crossing > largest_measured_size
                    else "inside_measured_range_but_not_observed"
                )
            else:
                status = "the lines diverge, so they never cross for a positive revision size"
        else:
            status = "no_projection_possible"
        if measure.startswith("total_seconds") and not resolved:
            condition = (
                "neither treatment shows a time trend the measured ranges can resolve, so no "
                "revision size inside or beyond this sweep can produce a crossing; only a change "
                "in the fixed cost could, that is the maintenance policy or the per-statement "
                "overhead, and neither was tested"
            )
        elif measure.startswith("total_seconds"):
            condition = (
                "the seconds of both treatments are flat in the revision size, so no revision size "
                "can produce a crossing; only a change in the fixed cost could, that is the "
                "maintenance policy or the per-statement overhead, and neither was tested"
            )
        elif projected:
            condition = (
                f"a crossing needs a revision touching about {projected} cells, against a panel of "
                f"{panel_cells} cells and a frozen universe of {largest_measured_size}"
            )
        else:
            condition = (
                "the comparator starts cheaper and stays cheaper as the revision grows, so no "
                f"revision size crosses; the panel holds {panel_cells} cells and the frozen "
                f"universe {largest_measured_size}"
            )
        rows.append(
            {
                "comparison": row["comparison"],
                "measure": measure,
                "measured_direction": row["direction"],
                "measured_crossing": row["crossing_cells"],
                "intercept_gap": f"{intercept_gap:.4f}",
                "slope_gap": f"{slope_gap:.4f}",
                "projected_crossing_cells": projected,
                "projection_status": status,
                "condition_for_a_crossing": condition,
            }
        )
    return rows


def cost_of_reproducibility(
    *,
    audit: list[dict[str, str]],
    profile: list[dict[str, str]],
    cases: list[dict[str, str]],
    decomposition: list[dict[str, str]],
    cost_rows: list[dict[str, str]],
    reads: list[dict[str, str]],
    real_cost: list[dict[str, str]],
) -> list[dict[str, str]]:
    panel = {row["treatment_id"]: row for row in audit if row["scale"] == "panel"}
    by_measure = {(row["treatment_id"], row["measure"]): row for row in decomposition}
    largest_read_point = sorted({row["scenario_id"] for row in reads})[-1]
    read_by_treatment = {
        row["treatment_id"]: row for row in reads if row["scenario_id"] == largest_read_point
    }
    rows: list[dict[str, str]] = []
    for treatment in TREATMENTS:
        if (treatment, "total_seconds_median") not in by_measure:
            raise ValueError(f"H14C has no cost decomposition for {treatment}")
        seconds = by_measure[(treatment, "total_seconds_median")]
        byte_line = by_measure[(treatment, "delta_bytes_median")]
        material = sum(
            int(row["material_failures"])
            for row in profile
            if row["treatment_id"] == treatment and row["failure_kind"] != SUPERSEDED
        )
        superseded = sum(
            1
            for row in cases
            if row["treatment_id"] == treatment and row["failure_kind"] == SUPERSEDED
        )
        real_seconds = sum(
            Decimal(row["total_seconds_median"])
            for row in real_cost
            if row["treatment_id"] == treatment
        )
        failures = int(panel[treatment]["failures"])
        if failures == 0 and material != 0:
            raise ValueError(f"{treatment} reports full recall but {material} material failures")
        rows.append(
            {
                "treatment_id": treatment,
                "panel_recall": panel[treatment]["success_rate"],
                "panel_failures": panel[treatment]["failures"],
                "material_failures": str(material),
                "superseded_serving_cells": str(superseded),
                "seconds_per_revision": seconds["intercept"],
                "maintenance_share": seconds["maintenance_share"],
                "bytes_per_revision_intercept": byte_line["intercept"],
                "bytes_per_revised_cell": byte_line["slope_per_revised_cell"],
                "bytes_read_per_revision": read_by_treatment[treatment]["bytes_read"],
                "real_releases_seconds": f"{real_seconds:.3f}",
                "verdict": (
                    "keeps every published figure"
                    if failures == 0
                    else "loses published figures by design"
                ),
            }
        )
    return rows


def synthesise_failures(
    *, profile: list[dict[str, str]], cases: list[dict[str, str]], costs: list[dict[str, str]]
) -> list[dict[str, str]]:
    keeping = [row["treatment_id"] for row in costs if row["panel_failures"] == "0"]
    cheapest_keeper = min(
        (row for row in costs if row["treatment_id"] in keeping),
        key=lambda row: Decimal(row["bytes_per_revision_intercept"]),
    )
    rows: list[dict[str, str]] = []
    for kind in sorted({row["failure_kind"] for row in profile}):
        selected = [row for row in profile if row["failure_kind"] == kind]
        treatments = sorted({row["treatment_id"] for row in selected})
        figures = sum(int(row["failures"]) for row in selected)
        material = sum(int(row["material_failures"]) for row in selected)
        if kind == SUPERSEDED:
            consequence = (
                "the request is answered, but with a value the producer has already replaced"
            )
        elif kind == "overwritten_by_later_vintage":
            consequence = "the published figure cannot be produced again from the treatment state"
        else:
            consequence = (
                "the published figure cannot be produced again because its source was not selected"
            )
        rows.append(
            {
                "failure_kind": kind,
                "treatments_affected": ";".join(treatments),
                "figures_affected": str(figures),
                "material_figures": str(material),
                "consequence": consequence,
                "treatments_free_of_it": ";".join(
                    treatment for treatment in TREATMENTS if treatment not in treatments
                ),
                "price_of_avoiding_it": (
                    f"{cheapest_keeper['treatment_id']} keeps every figure for "
                    f"{cheapest_keeper['bytes_per_revision_intercept']} bytes plus "
                    f"{cheapest_keeper['bytes_per_revised_cell']} per revised cell, at "
                    f"{cheapest_keeper['seconds_per_revision']} seconds per revision"
                ),
            }
        )
    return rows


def build_validation(
    *,
    contract: dict[str, Any],
    measured: list[dict[str, str]],
    conditions: list[dict[str, str]],
    decomposition: list[dict[str, str]],
    costs: list[dict[str, str]],
    audit: list[dict[str, str]],
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
        "the measured break-even answer is carried forward unchanged",
        all(row["measured_crossing"] == item["crossing_cells"] for row, item in zip(conditions, measured)),
        len(measured),
        ";".join(f"{row['comparison']}|{row['measure']}={row['crossing_cells']}" for row in measured),
    )
    projected = [row for row in conditions if row["projected_crossing_cells"]]
    add(
        "every projected crossing is labelled and none is presented as a break-even",
        all(row["projection_status"] != "" for row in projected)
        and all(row["measured_crossing"] == "none" for row in projected),
        len(projected),
        ";".join(
            f"{row['comparison']}|{row['measure']}={row['projected_crossing_cells']}({row['projection_status']})"
            for row in projected
        ),
    )
    add(
        "every slope is declared descriptive and names the sizes it was computed over",
        all(row["status"] == "descriptive" and row["sweep_sizes"] for row in decomposition),
        len(decomposition),
        decomposition[0]["sweep_sizes"] if decomposition else "",
    )
    panel = {row["treatment_id"]: row for row in audit if row["scale"] == "panel"}
    add(
        "recall is copied from the audit that measured it",
        all(row["panel_recall"] == panel[row["treatment_id"]]["success_rate"] for row in costs),
        len(costs),
        ";".join(f"{row['treatment_id']}={row['panel_recall']}" for row in costs),
    )
    add(
        "a treatment with full recall reports no material failure",
        all(
            row["material_failures"] == "0"
            for row in costs
            if row["panel_failures"] == "0"
        ),
        len(costs),
        ";".join(f"{row['treatment_id']}:{row['panel_failures']}/{row['material_failures']}" for row in costs),
    )
    return rows


def build_summary(
    *,
    decomposition: list[dict[str, str]],
    conditions: list[dict[str, str]],
    costs: list[dict[str, str]],
    failures: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in decomposition:
        measure = "seconds" if row["measure"].startswith("total_seconds") else "bytes"
        rows.append(
            {
                "metric": f"{row['treatment_id'].lower()}_{measure}_per_revision",
                "value": row["intercept"],
                "unit": "seconds" if measure == "seconds" else "bytes",
                "interpretation": (
                    f"plus {row['slope_per_revised_cell']} per revised cell over the "
                    f"{row['sweep_sizes']} sweep; observed {row['observed_min']} to {row['observed_max']}"
                    + (
                        f"; maintenance is {row['maintenance_share']} of the time"
                        if measure == "seconds" and row["maintenance_share"]
                        else ""
                    )
                ),
            }
        )
    for row in conditions:
        if not row["projected_crossing_cells"]:
            continue
        rows.append(
            {
                "metric": f"projection_{row['comparison'].replace(' ', '_')}_{row['measure']}",
                "value": row["projected_crossing_cells"],
                "unit": "cells",
                "interpretation": f"{row['projection_status']}; measured answer stays {row['measured_crossing']}",
            }
        )
    for row in costs:
        rows.append(
            {
                "metric": f"{row['treatment_id'].lower()}_cost_of_recall",
                "value": row["panel_recall"],
                "unit": "ratio",
                "interpretation": (
                    f"{row['bytes_per_revision_intercept']} bytes and {row['seconds_per_revision']} seconds "
                    f"per revision, {row['bytes_read_per_revision']} bytes read; {row['verdict']}"
                ),
            }
        )
    for row in failures:
        rows.append(
            {
                "metric": f"failure_{row['failure_kind']}",
                "value": row["material_figures"],
                "unit": "figures",
                "interpretation": (
                    f"{row['figures_affected']} figures affected on {row['treatments_affected']}; "
                    f"{row['consequence']}"
                ),
            }
        )
    return rows


def run_h14c(
    *,
    contract_path: Path,
    sweep_cost_path: Path,
    breakeven_path: Path,
    real_cost_path: Path,
    reads_path: Path,
    audit_path: Path,
    profile_path: Path,
    cases_path: Path,
    scenarios_path: Path,
    decomposition_output: Path,
    conditions_output: Path,
    cost_output: Path,
    failure_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)

    cost_rows = _read_csv(sweep_cost_path)
    measured = _read_csv(breakeven_path)
    scenarios = _read_csv(scenarios_path)
    audit = _read_csv(audit_path)
    decomposition = decompose(cost_rows, contract["decomposition"]["measures"])
    conditions = project_conditions(
        decomposition=decomposition,
        measured=measured,
        cost_rows=cost_rows,
        largest_measured_size=max(int(row["cells_revised"]) for row in cost_rows),
        panel_cells=int(scenarios[0]["panel_cells"]),
    )
    costs = cost_of_reproducibility(
        audit=audit,
        profile=_read_csv(profile_path),
        cases=_read_csv(cases_path),
        decomposition=decomposition,
        cost_rows=cost_rows,
        reads=_read_csv(reads_path),
        real_cost=_read_csv(real_cost_path),
    )
    failures = synthesise_failures(
        profile=_read_csv(profile_path), cases=_read_csv(cases_path), costs=costs
    )
    validation_rows = build_validation(
        contract=contract,
        measured=measured,
        conditions=conditions,
        decomposition=decomposition,
        costs=costs,
        audit=audit,
    )
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["invariant"] for row in validation_rows if row["status"] != "pass"]
        raise ValueError(f"H14C invariants failed: {failed}")
    summary_rows = build_summary(
        decomposition=decomposition, conditions=conditions, costs=costs, failures=failures
    )

    written = []
    for path, columns, rows in (
        (decomposition_output, DECOMPOSITION_COLUMNS, decomposition),
        (conditions_output, CONDITION_COLUMNS, conditions),
        (cost_output, REPRODUCIBILITY_COST_COLUMNS, costs),
        (failure_output, FAILURE_SYNTHESIS_COLUMNS, failures),
        (validation_output, VALIDATION_COLUMNS, validation_rows),
        (summary_output, SUMMARY_COLUMNS, summary_rows),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    manifest = {
        "stage": "H14",
        "track": "C",
        "contract_version": contract["contract_version"],
        "analysis_status": "validated",
        "measured_breakeven": {
            f"{row['comparison']}|{row['measure']}": row["crossing_cells"] for row in measured
        },
        "decomposition": {
            f"{row['treatment_id']}|{row['measure']}": {
                "intercept": row["intercept"],
                "slope_per_revised_cell": row["slope_per_revised_cell"],
            }
            for row in decomposition
        },
        "cost_of_recall": {
            row["treatment_id"]: {
                "panel_recall": row["panel_recall"],
                "bytes_per_revision_intercept": row["bytes_per_revision_intercept"],
                "seconds_per_revision": row["seconds_per_revision"],
            }
            for row in costs
        },
        "inputs": [
            _manifest_entry(path)
            for path in (
                contract_path,
                sweep_cost_path,
                breakeven_path,
                real_cost_path,
                reads_path,
                audit_path,
                profile_path,
                cases_path,
                scenarios_path,
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
        "treatments": len(TREATMENTS),
        "decomposition_rows": len(decomposition),
        "conditions": len(conditions),
        "projections": sum(1 for row in conditions if row["projected_crossing_cells"]),
        "measured_crossings": sum(1 for row in measured if row["crossing_cells"] != "none"),
        "failure_kinds": len(failures),
        "material_figures": sum(int(row["material_figures"]) for row in failures),
        "keeping_treatments": [row["treatment_id"] for row in costs if row["panel_failures"] == "0"],
        "status": "validated",
    }
