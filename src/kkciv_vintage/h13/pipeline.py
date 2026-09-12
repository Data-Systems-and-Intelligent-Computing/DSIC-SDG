from __future__ import annotations

import json
import statistics
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h11.pipeline import (
    SUMMARY_COLUMNS,
    TREATMENTS,
    VALIDATION_COLUMNS,
    _lines,
    _manifest_entry,
    _read_csv,
    _sha256,
    _write_csv,
    read_environment,
)
from kkciv_vintage.h11.pipeline import audit_injection as audit_h11_injection
from kkciv_vintage.h11.pipeline import audit_timing as audit_h11_timing
from kkciv_vintage.h12.pipeline import audit_states as audit_h12_states
from kkciv_vintage.h12.pipeline import audit_timing as audit_h12_timing
from kkciv_vintage.h12.pipeline import expected_states


DOUBT_COLUMNS = [
    "stage",
    "point_kind",
    "point",
    "treatment_id",
    "repetitions",
    "write_seconds_median",
    "write_seconds_min",
    "write_seconds_max",
    "write_spread_ratio",
    "maintenance_seconds_median",
    "maintenance_spread_ratio",
    "doubtful",
    "rerun_unit",
]
STABILITY_COLUMNS = [
    "stage",
    "point_kind",
    "point",
    "treatment_id",
    "was_doubtful",
    "repetitions_reported",
    "write_median_reported",
    "write_spread_reported",
    "repetitions_added",
    "repetitions_pooled",
    "write_median_pooled",
    "write_min_pooled",
    "write_max_pooled",
    "write_spread_pooled",
    "shift_ratio",
    "verdict",
]


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h13.1"
        or contract.get("stage") != "H13"
        or contract.get("track") != "B"
    ):
        raise ValueError("unsupported H13 contract")
    rule = contract["doubt_rule"]
    if rule["statistic"] != "write_spread_ratio" or not 0 < float(rule["threshold"]) < 1:
        raise ValueError("H13 needs a write-spread rule with a threshold between zero and one")
    if rule["rule_fixed_before_selection"] is not True:
        raise ValueError("the H13 doubt rule must be fixed before the points are selected")
    if contract["rerun"]["additional_repetitions"] < 1 or not contract["rerun"]["runs"]:
        raise ValueError("H13 must add repetitions and name the runs that provide them")
    verdict = contract["verdict"]
    if not 0 < float(verdict["stable_within"]) < 1:
        raise ValueError("H13 needs a stability band between zero and one")
    if "never in place of them" not in verdict["reported_medians_stay"]:
        raise ValueError("H13 must keep the reported medians alongside the pooled ones")


def phase_seconds(
    timing_rows: list[dict[str, str]], *, point_field: str
) -> dict[tuple[str, str], dict[str, dict[str, float]]]:
    """Sum the per-repetition seconds of every phase, per measurement point."""
    totals: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    for row in timing_rows:
        if row["phase"] not in {"write", "maintenance"}:
            continue
        key = (row[point_field], row["treatment_id"])
        totals[key][row["phase"]][row["repetition"]] += float(row["seconds"])
    return totals


def _spread(values: list[float]) -> tuple[float, float, float, float]:
    median = statistics.median(values)
    return median, min(values), max(values), (max(values) - min(values)) / median if median else 0.0


def apply_doubt_rule(
    *,
    stage: str,
    point_kind: str,
    point_field: str,
    timing_rows: list[dict[str, str]],
    threshold: float,
    rerun_unit: Any,
) -> list[dict[str, str]]:
    """Flag every point whose write-phase repetitions disagree beyond the threshold."""
    rows: list[dict[str, str]] = []
    totals = phase_seconds(timing_rows, point_field=point_field)
    for (point, treatment) in sorted(totals, key=lambda key: (key[0], key[1])):
        phases = totals[(point, treatment)]
        write = [phases["write"][rep] for rep in sorted(phases["write"])]
        maintenance = [phases["maintenance"].get(rep, 0.0) for rep in sorted(phases["write"])]
        median, low, high, ratio = _spread(write)
        upkeep_median, _, _, upkeep_ratio = _spread(maintenance) if any(maintenance) else (0.0, 0.0, 0.0, 0.0)
        doubtful = ratio > threshold
        rows.append(
            {
                "stage": stage,
                "point_kind": point_kind,
                "point": point,
                "treatment_id": treatment,
                "repetitions": str(len(write)),
                "write_seconds_median": f"{median:.3f}",
                "write_seconds_min": f"{low:.3f}",
                "write_seconds_max": f"{high:.3f}",
                "write_spread_ratio": f"{ratio:.4f}",
                "maintenance_seconds_median": f"{upkeep_median:.3f}",
                "maintenance_spread_ratio": f"{upkeep_ratio:.4f}",
                "doubtful": "yes" if doubtful else "no",
                "rerun_unit": rerun_unit(point) if doubtful else "",
            }
        )
    return rows


def pool_measurements(
    *,
    doubt_rows: list[dict[str, str]],
    reported: dict[str, list[dict[str, str]]],
    extra: dict[str, list[dict[str, str]]],
    point_fields: dict[str, str],
    stable_within: float,
) -> list[dict[str, str]]:
    """Put the extra repetitions next to the reported ones, never on top of them."""
    reported_totals = {
        stage: phase_seconds(rows, point_field=point_fields[stage]) for stage, rows in reported.items()
    }
    extra_totals = {
        stage: phase_seconds(rows, point_field=point_fields[stage]) for stage, rows in extra.items()
    }
    rows: list[dict[str, str]] = []
    for row in doubt_rows:
        stage = row["stage"]
        key = (row["point"], row["treatment_id"])
        added = extra_totals.get(stage, {}).get(key)
        reported_median = Decimal(row["write_seconds_median"])
        entry = {
            "stage": stage,
            "point_kind": row["point_kind"],
            "point": row["point"],
            "treatment_id": row["treatment_id"],
            "was_doubtful": row["doubtful"],
            "repetitions_reported": row["repetitions"],
            "write_median_reported": row["write_seconds_median"],
            "write_spread_reported": row["write_spread_ratio"],
            "repetitions_added": "0",
            "repetitions_pooled": row["repetitions"],
            "write_median_pooled": "",
            "write_min_pooled": "",
            "write_max_pooled": "",
            "write_spread_pooled": "",
            "shift_ratio": "",
            "verdict": "not_rerun",
        }
        if added is not None:
            measured = reported_totals[stage][key]["write"]
            reported_values = [measured[rep] for rep in sorted(measured)]
            added_values = [added["write"][rep] for rep in sorted(added["write"])]
            pooled = sorted(reported_values + added_values)
            median, low, high, ratio = _spread(pooled)
            shift = (Decimal(f"{median:.3f}") - reported_median) / reported_median
            entry.update(
                {
                    "repetitions_added": str(len(added_values)),
                    "repetitions_pooled": str(len(pooled)),
                    "write_median_pooled": f"{median:.3f}",
                    "write_min_pooled": f"{low:.3f}",
                    "write_max_pooled": f"{high:.3f}",
                    "write_spread_pooled": f"{ratio:.4f}",
                    "shift_ratio": f"{shift:.4f}",
                    "verdict": "stable" if abs(shift) <= Decimal(str(stable_within)) else "shifted",
                }
            )
        rows.append(entry)
    return rows


def build_validation(
    *,
    contract: dict[str, Any],
    doubt_rows: list[dict[str, str]],
    stability_rows: list[dict[str, str]],
    environments: dict[str, dict[str, str]],
    state_checks: dict[str, int],
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

    doubtful = [row for row in doubt_rows if row["doubtful"] == "yes"]
    add(
        "the doubt rule was applied to every measured point",
        True,
        len(doubt_rows),
        f"threshold {contract['doubt_rule']['threshold']} on {contract['doubt_rule']['statistic']}",
    )
    rerun = {row["point"] for row in stability_rows if row["repetitions_added"] != "0"}
    add(
        "every doubtful point was measured again",
        all(row["point"] in rerun for row in doubtful),
        len(doubtful),
        f"{len(doubtful)} doubtful points in {len({row['rerun_unit'] for row in doubtful})} rerun units",
    )
    add(
        "every rerun passed the state verification of its own stage",
        True,
        sum(state_checks.values()),
        ";".join(f"{stage}={count}" for stage, count in sorted(state_checks.items())),
    )
    # The reruns share one batch, so each one starts with the raw output of the reruns
    # before it already in the tree. Nothing else may be uncommitted, and all of them
    # must measure the same commit.
    ordered = [f"{run['stage'].lower()}_rerun" for run in contract["rerun"]["runs"]]
    commits = {environment.get("git_commit", "") for environment in environments.values()}
    clean = len(commits) == 1 and all(
        environments[label].get("host_nproc") == "2"
        and int(environments[label].get("git_dirty_entries", "0")) <= index
        for index, label in enumerate(ordered)
        if label in environments
    )
    add(
        "every rerun ran on the frozen node, from one commit, with nothing uncommitted but the raw output of the batch",
        clean,
        len(environments),
        ";".join(
            f"{label}:{environment.get('git_commit', '')[:7]}"
            f":dirty={environment.get('git_dirty_entries', '')}"
            for label, environment in sorted(environments.items())
        ),
    )
    add(
        "the reported medians are published next to the pooled ones, not replaced",
        all(row["write_median_reported"] for row in stability_rows),
        len(stability_rows),
        "h13-stability.csv keeps both columns for every point",
    )
    # A shift is what H13 exists to find, so it is reported rather than treated as a
    # harness failure. What must not happen is a shift that goes unrecorded.
    shifted = [row for row in stability_rows if row["verdict"] == "shifted"]
    add(
        "every pooled median outside the stability band is recorded for correction",
        all(row["shift_ratio"] and row["write_median_pooled"] for row in shifted),
        len([row for row in stability_rows if row["verdict"] != "not_rerun"]),
        (
            f"no median moved beyond {contract['verdict']['stable_within']} of its reported value"
            if not shifted
            else "shifted: "
            + ";".join(
                f"{row['stage']}|{row['point']}|{row['treatment_id']}|{row['write_median_reported']}"
                f"->{row['write_median_pooled']}|{row['shift_ratio']}"
                for row in shifted
            )
        ),
    )
    return rows


def build_summary(
    *, doubt_rows: list[dict[str, str]], stability_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    rerun = [row for row in stability_rows if row["verdict"] != "not_rerun"]
    rows = [
        {
            "metric": "points_checked",
            "value": str(len(doubt_rows)),
            "unit": "points",
            "interpretation": "every measurement point of H11 and H12, treatment by treatment",
        },
        {
            "metric": "points_doubtful",
            "value": str(sum(1 for row in doubt_rows if row["doubtful"] == "yes")),
            "unit": "points",
            "interpretation": "write-phase repetitions disagreeing by more than the frozen threshold",
        },
        {
            "metric": "points_rerun",
            "value": str(len(rerun)),
            "unit": "points",
            "interpretation": "points that received additional repetitions, including those measured in the same cycle",
        },
        {
            "metric": "points_stable",
            "value": str(sum(1 for row in rerun if row["verdict"] == "stable")),
            "unit": "points",
            "interpretation": "pooled median within the stability band of the reported median",
        },
        {
            "metric": "points_shifted",
            "value": str(sum(1 for row in rerun if row["verdict"] == "shifted")),
            "unit": "points",
            "interpretation": "pooled median outside the band; the article must correct these",
        },
    ]
    for row in sorted(rerun, key=lambda item: abs(Decimal(item["shift_ratio"])), reverse=True)[:8]:
        rows.append(
            {
                "metric": f"shift_{row['stage'].lower()}_{row['point']}_{row['treatment_id'].lower()}",
                "value": row["shift_ratio"],
                "unit": "ratio",
                "interpretation": (
                    f"reported {row['write_median_reported']} s over {row['repetitions_reported']} runs, "
                    f"pooled {row['write_median_pooled']} s over {row['repetitions_pooled']} runs, "
                    f"spread {row['write_spread_reported']} to {row['write_spread_pooled']}"
                ),
            }
        )
    return rows


def run_h13(
    *,
    contract_path: Path,
    h11_timing_path: Path,
    h12_timing_path: Path,
    h11_payload_manifest: Path,
    h11_rerun_dir: Path,
    h12_rerun_dir: Path,
    doubt_output: Path,
    stability_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    threshold = float(contract["doubt_rule"]["threshold"])
    added = contract["rerun"]["additional_repetitions"]

    h11_rows = _read_csv(h11_timing_path)
    h12_rows = _read_csv(h12_timing_path)
    doubt_rows = [
        *apply_doubt_rule(
            stage="H11",
            point_kind="sweep_scenario",
            point_field="scenario_id",
            timing_rows=h11_rows,
            threshold=threshold,
            rerun_unit=lambda point: point,
        ),
        *apply_doubt_rule(
            stage="H12",
            point_kind="release_arrival",
            point_field="arrival_order",
            timing_rows=h12_rows,
            threshold=threshold,
            rerun_unit=lambda point: "all_arrivals",
        ),
    ]

    payload = json.loads(h11_payload_manifest.read_text(encoding="utf-8"))
    outputs = {Path(item["path"]).name: Path(item["path"]) for item in payload["outputs"]}
    expectations = _read_csv(outputs["h11-sweep-scenarios.csv"])
    catalog = _read_csv(outputs["h11-b1-state-catalog.csv"])

    scenarios = sorted({row["point"] for row in doubt_rows if row["stage"] == "H11" and row["doubtful"] == "yes"})
    declared = sorted(
        scenario
        for run in contract["rerun"]["runs"]
        if run["stage"] == "H11"
        for scenario in run["scenarios"]
    )
    if scenarios != declared:
        raise ValueError(
            f"the H11 rerun covers {declared} while the doubt rule selects {scenarios}"
        )
    h11_extra = audit_h11_timing(
        _lines(h11_rerun_dir / "timing.txt", "H11T"), repetitions=added, scenarios=scenarios
    )
    h11_states = audit_h11_injection(
        lines=_lines(h11_rerun_dir / "injection.txt", "H11I"),
        repetitions=added,
        expectations=[row for row in expectations if row["scenario_id"] in scenarios],
    )
    h12_extra = audit_h12_timing(
        _lines(h12_rerun_dir / "timing.txt", "H12T"), repetitions=added, arrivals=4
    )
    h12_states = audit_h12_states(
        _lines(h12_rerun_dir / "arrivals.txt", "H12A"),
        repetitions=added,
        arrivals=4,
        expectations=expected_states(catalog),
        tables={
            "B0": ["kkciv.sweep.b0_panel_current"],
            "B1": ["kkciv.sweep.b1_panel_full_snapshots"],
            "B2": ["kkciv.sweep.b2_panel_selected"],
            "B3": [
                "kkciv.sweep.b3_panel_observation_vintages",
                "kkciv.sweep.b3_panel_current",
            ],
        },
    )

    stability_rows = pool_measurements(
        doubt_rows=doubt_rows,
        reported={"H11": h11_rows, "H12": h12_rows},
        extra={"H11": h11_extra, "H12": h12_extra},
        point_fields={"H11": "scenario_id", "H12": "arrival_order"},
        stable_within=float(contract["verdict"]["stable_within"]),
    )
    environments = {
        "h11_rerun": read_environment(h11_rerun_dir / "environment.txt"),
        "h12_rerun": read_environment(h12_rerun_dir / "environment.txt"),
    }
    validation_rows = build_validation(
        contract=contract,
        doubt_rows=doubt_rows,
        stability_rows=stability_rows,
        environments=environments,
        state_checks={"H11": len(h11_states), "H12": len(h12_states)},
    )
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["invariant"] for row in validation_rows if row["status"] != "pass"]
        raise ValueError(f"H13 invariants failed: {failed}")
    summary_rows = build_summary(doubt_rows=doubt_rows, stability_rows=stability_rows)

    written = []
    for path, columns, rows in (
        (doubt_output, DOUBT_COLUMNS, doubt_rows),
        (stability_output, STABILITY_COLUMNS, stability_rows),
        (validation_output, VALIDATION_COLUMNS, validation_rows),
        (summary_output, SUMMARY_COLUMNS, summary_rows),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    manifest = {
        "stage": "H13",
        "track": "B",
        "contract_version": contract["contract_version"],
        "execution_status": "rerun_completed",
        "doubt_rule": contract["doubt_rule"],
        "environments": environments,
        "inputs": [
            _manifest_entry(path)
            for path in (contract_path, h11_timing_path, h12_timing_path, h11_payload_manifest)
        ],
        "raw_inputs": [
            _manifest_entry(path)
            for directory in (h11_rerun_dir, h12_rerun_dir)
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        ],
        "outputs": written,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rerun = [row for row in stability_rows if row["verdict"] != "not_rerun"]
    return {
        "points_checked": len(doubt_rows),
        "points_doubtful": sum(1 for row in doubt_rows if row["doubtful"] == "yes"),
        "points_rerun": len(rerun),
        "points_stable": sum(1 for row in rerun if row["verdict"] == "stable"),
        "points_shifted": sum(1 for row in rerun if row["verdict"] == "shifted"),
        "repetitions_added": added,
        "largest_shift": max(
            (row["shift_ratio"] for row in rerun), key=lambda value: abs(Decimal(value)), default="0"
        ),
        "status": "verified",
    }
