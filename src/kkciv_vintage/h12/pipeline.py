from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h11.pipeline import (
    SUMMARY_COLUMNS,
    TREATMENTS,
    VALIDATION_COLUMNS,
    _lines,
    _manifest_entry,
    _median_int,
    _median_seconds,
    _read_csv,
    _sha256,
    _write_csv,
    read_environment,
    verify_freeze,
)


SIZED_CLASSES = {"data", "delete", "manifest"}
TIMING_COLUMNS = [
    "repetition",
    "treatment_id",
    "arrival_order",
    "statement_index",
    "statement_label",
    "phase",
    "seconds",
]
STATE_COLUMNS = [
    "repetition",
    "treatment_id",
    "table",
    "arrival_order",
    "rows",
    "cells",
    "snapshots",
    "data_bytes",
    "manifest_bytes",
]
ARRIVAL_COST_COLUMNS = [
    "arrival_order",
    "source_id",
    "vintage_date",
    "arriving_rows",
    "overwritten_rows",
    "value_changed_rows",
    "same_value_overwrites",
    "treatment_id",
    "write_statements",
    "write_seconds_median",
    "write_seconds_min",
    "write_seconds_max",
    "maintenance_seconds_median",
    "total_seconds_median",
    "rows_after",
    "cells_after",
    "snapshots_after",
    "referenced_bytes_after",
    "referenced_bytes_added",
]
FOOTPRINT_COLUMNS = [
    "treatment_id",
    "table",
    "objects",
    "total_bytes",
    "data_bytes",
    "metadata_bytes",
    "unreferenced_objects",
    "unreferenced_bytes",
]


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h12.1"
        or contract.get("stage") != "H12"
        or contract.get("track") != "B"
    ):
        raise ValueError("unsupported H12 contract")
    if contract["workload"]["arrivals"] != 4 or contract["workload"]["observations"] != 6983:
        raise ValueError("H12 must apply the four real releases of the frozen panel")
    if list(contract["tables"]) != TREATMENTS:
        raise ValueError("H12 must measure B0 B1 B2 and B3")
    if set(contract["protocol"]["per_arrival"]) != set(TREATMENTS):
        raise ValueError("H12 needs a per-arrival mechanism for every treatment")
    if contract["protocol"]["repetitions"] < 3:
        raise ValueError("H12 requires at least three repetitions")
    if contract["measurement_boundary"]["revision_kind"] != "real_releases_only":
        raise ValueError("H12 measures real releases; the injected sweep stays with H11")
    if contract["timing"]["environment_decision"] != "h10b_timing_environment":
        raise ValueError("H12 timing must cite the frozen environment decision")


def expected_states(catalog: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    """Derive, from the frozen panel catalog, the state every treatment must hold.

    The catalog records what each real release brings and what the complete state looks
    like afterwards, so the expectation never comes from the measurement itself.
    """
    ordered = sorted(catalog, key=lambda row: int(row["snapshot_order"]))
    expectations: dict[tuple[str, str], dict[str, str]] = {}
    cumulative_rows = 0
    cumulative_states = 0
    for row in ordered:
        arrival = row["snapshot_order"]
        state_rows = int(row["state_rows"])
        cumulative_rows += int(row["input_rows"])
        cumulative_states += state_rows
        expectations[("B0", arrival)] = {
            "rows": str(state_rows),
            "cells": str(state_rows),
            "snapshots": "1",
        }
        expectations[("B1", arrival)] = {
            "rows": str(cumulative_states),
            "cells": str(state_rows),
            "snapshots": arrival,
        }
        expectations[("B2", arrival)] = {
            "rows": str(state_rows),
            "cells": str(state_rows),
            "snapshots": "1",
        }
        expectations[("B3_store", arrival)] = {
            "rows": str(cumulative_rows),
            "cells": str(state_rows),
            "snapshots": "1",
        }
        expectations[("B3_serving", arrival)] = {
            "rows": str(state_rows),
            "cells": str(state_rows),
            "snapshots": "1",
        }
    return expectations


def audit_timing(
    lines: list[list[str]], *, repetitions: int, arrivals: int
) -> list[dict[str, str]]:
    expected_labels = {
        "B0": ["merge_arrival", "expire_snapshots", "verify_state"],
        "B1": ["insert_overwrite_all_states", "verify_state"],
        "B2": [
            "narrow_candidates",
            "insert_overwrite_selection",
            "expire_snapshots",
            "verify_state",
        ],
        "B3": [
            "insert_store_rows",
            "merge_serving_dirty_cells",
            "expire_snapshots_store",
            "expire_snapshots_serving",
            "verify_store",
            "verify_serving",
        ],
    }
    rows: list[dict[str, str]] = []
    seen: dict[tuple[str, str, str], list[str]] = {}
    for _, rep, treatment, arrival, index, label, phase, seconds in lines:
        if int(rep) < 1 or int(rep) > repetitions or treatment not in TREATMENTS:
            raise ValueError(f"unexpected H12 timing row for rep {rep} {treatment}")
        if phase not in {"harness", "write", "maintenance", "verification"}:
            raise ValueError(f"unexpected H12 timing phase {phase}")
        float(seconds)
        if label != "staging_views":
            seen.setdefault((rep, treatment, arrival), []).append(label)
        rows.append(
            {
                "repetition": rep,
                "treatment_id": treatment,
                "arrival_order": arrival,
                "statement_index": index,
                "statement_label": label,
                "phase": phase,
                "seconds": seconds,
            }
        )
    for rep in range(1, repetitions + 1):
        for treatment in TREATMENTS:
            for arrival in range(1, arrivals + 1):
                labels = seen.get((str(rep), treatment, str(arrival)))
                if labels != expected_labels[treatment]:
                    raise ValueError(
                        f"H12 {treatment} did not issue its frozen statements on arrival "
                        f"{arrival} of repetition {rep}"
                    )
    return rows


def audit_states(
    lines: list[list[str]],
    *,
    repetitions: int,
    arrivals: int,
    expectations: dict[tuple[str, str], dict[str, str]],
    tables: dict[str, list[str]],
) -> list[dict[str, str]]:
    store_table, serving_table = tables["B3"]
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for _, rep, treatment, table, arrival, count, cells, snapshots, data_bytes, manifest_bytes in lines:
        if int(rep) < 1 or int(rep) > repetitions or treatment not in TREATMENTS:
            raise ValueError(f"unexpected H12 state row for rep {rep} {treatment}")
        key = treatment
        if treatment == "B3":
            key = "B3_store" if table == store_table else "B3_serving"
        expectation = expectations.get((key, arrival))
        if expectation is None:
            raise ValueError(f"H12 has no expectation for {key} arrival {arrival}")
        if (count, cells, snapshots) != (
            expectation["rows"],
            expectation["cells"],
            expectation["snapshots"],
        ):
            raise ValueError(
                f"H12 {key} after arrival {arrival} holds {count} rows over {cells} cells in "
                f"{snapshots} snapshots instead of {expectation}"
            )
        seen.add((rep, table, arrival))
        rows.append(
            {
                "repetition": rep,
                "treatment_id": treatment,
                "table": table,
                "arrival_order": arrival,
                "rows": count,
                "cells": cells,
                "snapshots": snapshots,
                "data_bytes": data_bytes,
                "manifest_bytes": manifest_bytes,
            }
        )
    tables_measured = {table for _, table, _ in seen}
    if len(seen) != repetitions * arrivals * len(tables_measured):
        raise ValueError("H12 did not record every table after every arrival of every repetition")
    return rows


def audit_footprint(
    *,
    footprint_lines: list[list[str]],
    listing_lines: list[list[str]],
    repetitions: int,
) -> list[dict[str, str]]:
    listing: dict[tuple[str, str], dict[str, int]] = {}
    for _, rep, _treatment, table, path, size in listing_lines:
        listing.setdefault((rep, table), {})[path] = int(size)
    reachable: dict[tuple[str, str], dict[str, tuple[int, str]]] = {}
    for _, rep, treatment, table, object_class, path, metadata_size in footprint_lines:
        objects = listing.get((rep, table), {})
        if path not in objects:
            raise ValueError(f"metadata references a missing object {path}")
        if object_class in SIZED_CLASSES and int(metadata_size) != objects[path]:
            raise ValueError(f"metadata size differs from the MinIO object size for {path}")
        reachable.setdefault((rep, table), {})[path] = (objects[path], object_class)
        reachable[(rep, table)][path] = (objects[path], object_class)

    treatments_by_table = {
        table: treatment for _, _rep, treatment, table, _class, _path, _size in footprint_lines
    }
    rows: list[dict[str, str]] = []
    for table in sorted(treatments_by_table):
        totals: dict[str, list[int]] = {
            "objects": [],
            "total": [],
            "data": [],
            "metadata": [],
            "unreferenced_objects": [],
            "unreferenced_bytes": [],
        }
        for rep in [str(index) for index in range(1, repetitions + 1)]:
            objects = reachable[(rep, table)]
            listed = listing[(rep, table)]
            unreferenced = {path: size for path, size in listed.items() if path not in objects}
            totals["objects"].append(len(objects))
            totals["total"].append(sum(size for size, _ in objects.values()))
            totals["data"].append(
                sum(size for size, kind in objects.values() if kind in {"data", "delete"})
            )
            totals["metadata"].append(
                sum(size for size, kind in objects.values() if kind not in {"data", "delete"})
            )
            totals["unreferenced_objects"].append(len(unreferenced))
            totals["unreferenced_bytes"].append(sum(unreferenced.values()))
        rows.append(
            {
                "treatment_id": treatments_by_table[table],
                "table": table,
                "objects": str(_median_int(totals["objects"])),
                "total_bytes": str(_median_int(totals["total"])),
                "data_bytes": str(_median_int(totals["data"])),
                "metadata_bytes": str(_median_int(totals["metadata"])),
                "unreferenced_objects": str(_median_int(totals["unreferenced_objects"])),
                "unreferenced_bytes": str(_median_int(totals["unreferenced_bytes"])),
            }
        )
    return rows


def aggregate_arrival_cost(
    *,
    timing_rows: list[dict[str, str]],
    state_rows: list[dict[str, str]],
    catalog: list[dict[str, str]],
    repetitions: int,
) -> list[dict[str, str]]:
    catalog_by_arrival = {row["snapshot_order"]: row for row in catalog}
    reps = [str(index) for index in range(1, repetitions + 1)]
    seconds: dict[tuple[str, str, str, str], float] = {}
    write_statements: dict[tuple[str, str], int] = {}
    for row in timing_rows:
        if row["phase"] not in {"write", "maintenance"}:
            continue
        key = (row["treatment_id"], row["arrival_order"], row["repetition"], row["phase"])
        seconds[key] = seconds.get(key, 0.0) + float(row["seconds"])
        if row["phase"] == "write" and row["repetition"] == reps[0]:
            statement_key = (row["treatment_id"], row["arrival_order"])
            write_statements[statement_key] = write_statements.get(statement_key, 0) + 1

    referenced: dict[tuple[str, str, str], int] = {}
    for row in state_rows:
        key = (row["treatment_id"], row["arrival_order"], row["repetition"])
        referenced[key] = referenced.get(key, 0) + int(row["data_bytes"]) + int(row["manifest_bytes"])
    state_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in state_rows:
        if row["repetition"] != reps[0]:
            continue
        key = (row["treatment_id"], row["arrival_order"])
        entry = state_by_key.setdefault(key, {"rows": 0, "cells": 0, "snapshots": 0})
        entry["rows"] += int(row["rows"])
        entry["cells"] = max(entry["cells"], int(row["cells"]))
        entry["snapshots"] = max(entry["snapshots"], int(row["snapshots"]))

    # audit_timing has already checked that every treatment issued its frozen statements,
    # so iterating over what was measured keeps this step composable.
    measured = [treatment for treatment in TREATMENTS if any(row["treatment_id"] == treatment for row in timing_rows)]
    rows: list[dict[str, str]] = []
    for arrival in sorted(catalog_by_arrival, key=int):
        catalog_row = catalog_by_arrival[arrival]
        for treatment in measured:
            write_values = [seconds.get((treatment, arrival, rep, "write"), 0.0) for rep in reps]
            maintenance_values = [
                seconds.get((treatment, arrival, rep, "maintenance"), 0.0) for rep in reps
            ]
            totals = [write + upkeep for write, upkeep in zip(write_values, maintenance_values)]
            after = _median_int([referenced[(treatment, arrival, rep)] for rep in reps])
            previous_arrival = str(int(arrival) - 1)
            before = (
                _median_int([referenced[(treatment, previous_arrival, rep)] for rep in reps])
                if (treatment, previous_arrival, reps[0]) in referenced
                else 0
            )
            state = state_by_key[(treatment, arrival)]
            rows.append(
                {
                    "arrival_order": arrival,
                    "source_id": catalog_row["source_id"],
                    "vintage_date": catalog_row["vintage_date"],
                    "arriving_rows": catalog_row["input_rows"],
                    "overwritten_rows": catalog_row["overwritten_rows"],
                    "value_changed_rows": catalog_row["value_changed_rows"],
                    "same_value_overwrites": catalog_row["same_value_overwrites"],
                    "treatment_id": treatment,
                    "write_statements": str(write_statements[(treatment, arrival)]),
                    "write_seconds_median": _median_seconds(write_values),
                    "write_seconds_min": f"{min(write_values):.3f}",
                    "write_seconds_max": f"{max(write_values):.3f}",
                    "maintenance_seconds_median": _median_seconds(maintenance_values),
                    "total_seconds_median": _median_seconds(totals),
                    "rows_after": str(state["rows"]),
                    "cells_after": str(state["cells"]),
                    "snapshots_after": str(state["snapshots"]),
                    "referenced_bytes_after": str(after),
                    "referenced_bytes_added": str(after - before),
                }
            )
    return rows


def build_validation(
    *,
    contract: dict[str, Any],
    environment: dict[str, str],
    freeze_rows: list[dict[str, str]],
    timing_rows: list[dict[str, str]],
    state_rows: list[dict[str, str]],
    footprint_rows: list[dict[str, str]],
    baseline: list[dict[str, str]],
) -> list[dict[str, str]]:
    repetitions = contract["protocol"]["repetitions"]
    arrivals = str(contract["workload"]["arrivals"])
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
        "frozen evidence still matches the freeze checksums",
        True,
        len(freeze_rows),
        f"{len(freeze_rows)} frozen items re-checked before the run was aggregated",
    )
    add(
        "every arrival leaves the state the frozen panel implies",
        True,
        len(state_rows),
        "row, cell and snapshot counts checked against the panel catalog on every arrival",
    )
    expected_final = {row["table"]: row["expected_rows"] for row in baseline}
    final = {
        row["table"]: row["rows"]
        for row in state_rows
        if row["arrival_order"] == arrivals and row["repetition"] == "1"
    }
    add(
        "the state after the last real release equals the H11 baseline",
        final == expected_final,
        len(final),
        f"{sorted(final.items())}",
    )
    identical = all(
        len(
            {
                (row["rows"], row["cells"], row["snapshots"])
                for row in state_rows
                if row["table"] == table and row["arrival_order"] == arrival
            }
        )
        == 1
        for table in {row["table"] for row in state_rows}
        for arrival in {row["arrival_order"] for row in state_rows}
    )
    add(
        "every repetition reproduces the same state after every arrival",
        identical,
        len(state_rows),
        f"{repetitions} repetitions over {arrivals} arrivals",
    )
    add(
        "every metadata-referenced object exists in MinIO with the size metadata records",
        True,
        len(footprint_rows),
        "checked while folding the final footprint",
    )
    add(
        "no unreferenced object is counted as stored space",
        all(row["unreferenced_bytes"] == "0" for row in footprint_rows),
        len(footprint_rows),
        ";".join(f"{row['table'].split('.')[-1]}={row['unreferenced_objects']}" for row in footprint_rows),
    )
    add(
        "the run stayed on the frozen resource limit",
        environment.get("host_nproc") == "2" and environment.get("limited_run", "no") == "no",
        1,
        f"nproc={environment.get('host_nproc')}, driver={environment.get('spark_driver_memory')}, "
        f"catalog={environment.get('catalog_uri')}",
    )
    add(
        "the working tree was clean when the measurement started",
        environment.get("git_dirty_entries") == "0",
        1,
        f"commit {environment.get('git_commit')}",
    )
    add(
        "all repetitions are reported before any aggregation",
        len({row["repetition"] for row in timing_rows}) == repetitions,
        len(timing_rows),
        f"{repetitions} repetitions of {arrivals} arrivals and {len(TREATMENTS)} treatments",
    )
    return rows


def build_summary(
    *, cost_rows: list[dict[str, str]], footprint_rows: list[dict[str, str]], environment: dict[str, str]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {
            "metric": "host_nproc",
            "value": environment.get("host_nproc", ""),
            "unit": "vCPU",
            "interpretation": "declared timing environment; comparison between treatments only",
        }
    ]
    for treatment in TREATMENTS:
        selected = [row for row in cost_rows if row["treatment_id"] == treatment]
        total = sum(Decimal(row["total_seconds_median"]) for row in selected)
        rows.append(
            {
                "metric": f"{treatment.lower()}_all_arrivals_total_seconds",
                "value": f"{total:.3f}",
                "unit": "seconds",
                "interpretation": "sum of the median write and maintenance time of the four real releases",
            }
        )
        rows.append(
            {
                "metric": f"{treatment.lower()}_referenced_bytes_after_last_release",
                "value": selected[-1]["referenced_bytes_after"],
                "unit": "bytes",
                "interpretation": "data and manifest bytes the metadata still references after the last release",
            }
        )
    for row in footprint_rows:
        rows.append(
            {
                "metric": f"footprint_{row['table'].split('.')[-1]}",
                "value": row["total_bytes"],
                "unit": "bytes",
                "interpretation": (
                    f"{row['objects']} objects; data {row['data_bytes']}; metadata {row['metadata_bytes']}"
                ),
            }
        )
    return rows


def run_aggregate(
    *,
    contract_path: Path,
    freeze_path: Path,
    payload_manifest_path: Path,
    raw_dir: Path,
    timing_output: Path,
    state_output: Path,
    cost_output: Path,
    footprint_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    freeze_rows = _read_csv(freeze_path)
    verify_freeze(freeze_rows, [])

    payload = json.loads(payload_manifest_path.read_text(encoding="utf-8"))
    if payload.get("stage") != "H11" or payload.get("payload_status") != "prepared":
        raise ValueError("H12 needs the prepared H11 panel payload")
    outputs = {}
    for item in payload["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested payload output {path}")
        outputs[path.name] = path
    catalog = _read_csv(outputs["h11-b1-state-catalog.csv"])
    baseline = _read_csv(outputs["h11-baseline-expectations.csv"])

    environment = read_environment(raw_dir / "environment.txt")
    repetitions = contract["protocol"]["repetitions"]
    arrivals = contract["workload"]["arrivals"]
    if environment.get("repetitions") != str(repetitions):
        raise ValueError("the raw run did not use the frozen repetition count")
    if environment.get("arrivals") != str(arrivals):
        raise ValueError("the raw run did not apply the four real releases")
    if environment.get("limited_run", "no") != "no":
        raise ValueError("a limited run can never be aggregated as the H12 measurement")

    timing_rows = audit_timing(
        _lines(raw_dir / "timing.txt", "H12T"), repetitions=repetitions, arrivals=arrivals
    )
    state_rows = audit_states(
        _lines(raw_dir / "arrivals.txt", "H12A"),
        repetitions=repetitions,
        arrivals=arrivals,
        expectations=expected_states(catalog),
        tables=contract["tables"],
    )
    footprint_rows = audit_footprint(
        footprint_lines=_lines(raw_dir / "footprint.txt", "H12F"),
        listing_lines=_lines(raw_dir / "listing.txt", "H12L"),
        repetitions=repetitions,
    )
    cost_rows = aggregate_arrival_cost(
        timing_rows=timing_rows,
        state_rows=state_rows,
        catalog=catalog,
        repetitions=repetitions,
    )
    validation_rows = build_validation(
        contract=contract,
        environment=environment,
        freeze_rows=freeze_rows,
        timing_rows=timing_rows,
        state_rows=state_rows,
        footprint_rows=footprint_rows,
        baseline=baseline,
    )
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["invariant"] for row in validation_rows if row["status"] != "pass"]
        raise ValueError(f"H12 invariants failed: {failed}")
    summary_rows = build_summary(
        cost_rows=cost_rows, footprint_rows=footprint_rows, environment=environment
    )

    written = []
    for path, columns, rows in (
        (timing_output, TIMING_COLUMNS, timing_rows),
        (state_output, STATE_COLUMNS, state_rows),
        (cost_output, ARRIVAL_COST_COLUMNS, cost_rows),
        (footprint_output, FOOTPRINT_COLUMNS, footprint_rows),
        (validation_output, VALIDATION_COLUMNS, validation_rows),
        (summary_output, SUMMARY_COLUMNS, summary_rows),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    totals = {
        treatment: f"{sum(Decimal(row['total_seconds_median']) for row in cost_rows if row['treatment_id'] == treatment):.3f}"
        for treatment in TREATMENTS
    }
    final_bytes = {
        treatment: next(
            row["referenced_bytes_after"]
            for row in reversed(cost_rows)
            if row["treatment_id"] == treatment
        )
        for treatment in TREATMENTS
    }
    manifest = {
        "stage": "H12",
        "track": "B",
        "contract_version": contract["contract_version"],
        "execution_status": "executed_physical",
        "environment": environment,
        "arrival_cost": {
            f"{row['arrival_order']}|{row['treatment_id']}": {
                key: row[key]
                for key in ("write_seconds_median", "maintenance_seconds_median", "total_seconds_median", "referenced_bytes_added")
            }
            for row in cost_rows
        },
        "inputs": [
            _manifest_entry(path) for path in (contract_path, freeze_path, payload_manifest_path)
        ],
        "raw_inputs": [
            _manifest_entry(path) for path in sorted(raw_dir.rglob("*")) if path.is_file()
        ],
        "outputs": written,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "repetitions": repetitions,
        "arrivals": arrivals,
        "statements": len(timing_rows),
        "totals": totals,
        "final_bytes": final_bytes,
        "value_changed_rows": sum(int(row["value_changed_rows"]) for row in catalog),
        "status": "measured",
    }
