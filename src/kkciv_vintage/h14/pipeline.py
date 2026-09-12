from __future__ import annotations

import json
import re
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


READ_COLUMNS = [
    "repetition",
    "scenario_id",
    "treatment_id",
    "execution_id",
    "statement",
    "iceberg_bytes_read",
    "file_bytes_read",
    "bytes_read",
    "delete_bytes_read",
    "data_files_read",
    "data_files_skipped",
    "output_rows",
    "file_records_read",
]
READ_SUMMARY_COLUMNS = [
    "scenario_id",
    "treatment_id",
    "executions",
    "iceberg_bytes_read",
    "file_bytes_read",
    "bytes_read",
    "delete_bytes_read",
    "data_files_read",
    "data_files_skipped",
    "output_rows",
    "repetitions_agreeing",
]
PLAN_COLUMNS = [
    "scenario_id",
    "treatment_id",
    "plan_path",
    "plan_sha256",
    "plan_lines",
    "top_operator",
    "copy_on_write_rewrite",
    "join_operators",
    "repetitions_agreeing",
]
ARTIFACT_COLUMNS = ["kind", "path", "bytes", "sha256"]
JOIN_PATTERN = re.compile(r"\b(SortMergeJoin|BroadcastHashJoin|ShuffledHashJoin|BroadcastNestedLoopJoin)\b")


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h14.1"
        or contract.get("stage") != "H14"
        or contract.get("track") != "B"
    ):
        raise ValueError("unsupported H14 contract")
    instrumentation = contract["instrumentation"]
    if instrumentation["event_log"]["enabled"] is not True:
        raise ValueError("H14 reads its statistics from the Spark event log")
    if instrumentation["read_statistics"]["closes_metric"] != "s2":
        raise ValueError("H14 exists to close the bytes-read metric")
    if contract["measurement_boundary"]["timing"] != "not_reported; this run is instrumented and its seconds are not comparable with the frozen timing runs":
        raise ValueError("an instrumented run may never report timing")
    if contract["protocol"]["repetitions"] < 2:
        raise ValueError("H14 needs at least two repetitions to show the statistics are stable")
    if not contract["workload"]["scenarios"]:
        raise ValueError("H14 needs at least one frozen sweep point")


def audit_read_statistics(
    lines: list[list[str]], *, repetitions: int, scenarios: list[str]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    for (
        _,
        rep,
        scenario,
        treatment,
        execution,
        iceberg_read,
        file_read,
        delete_read,
        files,
        skipped,
        output,
        file_records,
        statement,
    ) in lines:
        if int(rep) < 1 or int(rep) > repetitions or scenario not in scenarios:
            raise ValueError(f"unexpected H14 read row for rep {rep} {scenario}")
        if treatment not in TREATMENTS:
            raise ValueError(f"unexpected H14 read row for treatment {treatment}")
        rows.append(
            {
                "repetition": rep,
                "scenario_id": scenario,
                "treatment_id": treatment,
                "execution_id": execution,
                "statement": statement,
                "iceberg_bytes_read": iceberg_read,
                "file_bytes_read": file_read,
                # What the statement reads in total: its own table plus the staging files.
                "bytes_read": str(int(iceberg_read) + int(file_read)),
                "delete_bytes_read": delete_read,
                "data_files_read": files,
                "data_files_skipped": skipped,
                "output_rows": output,
                "file_records_read": file_records,
            }
        )

    totals: dict[tuple[str, str, str], dict[str, int]] = {}
    for row in rows:
        key = (row["scenario_id"], row["treatment_id"], row["repetition"])
        entry = totals.setdefault(
            key,
            {
                "executions": 0,
                "iceberg_bytes_read": 0,
                "file_bytes_read": 0,
                "bytes_read": 0,
                "delete_bytes_read": 0,
                "data_files_read": 0,
                "data_files_skipped": 0,
                "output_rows": 0,
            },
        )
        entry["executions"] += 1
        for column in (
            "iceberg_bytes_read",
            "file_bytes_read",
            "bytes_read",
            "delete_bytes_read",
            "data_files_read",
            "data_files_skipped",
            "output_rows",
        ):
            entry[column] += int(row[column])

    summary: list[dict[str, str]] = []
    for scenario in scenarios:
        for treatment in TREATMENTS:
            measured = [
                totals[(scenario, treatment, str(rep))]
                for rep in range(1, repetitions + 1)
                if (scenario, treatment, str(rep)) in totals
            ]
            if len(measured) != repetitions:
                raise ValueError(f"H14 has no read statistics for {treatment} at {scenario} in every repetition")
            distinct = {tuple(sorted(entry.items())) for entry in measured}
            if len(distinct) != 1:
                raise ValueError(
                    f"H14 read statistics for {treatment} at {scenario} differ between repetitions: {measured}"
                )
            entry = measured[0]
            if entry["bytes_read"] <= 0:
                raise ValueError(f"H14 measured no read bytes for {treatment} at {scenario}")
            summary.append(
                {
                    "scenario_id": scenario,
                    "treatment_id": treatment,
                    "executions": str(entry["executions"]),
                    "iceberg_bytes_read": str(entry["iceberg_bytes_read"]),
                    "file_bytes_read": str(entry["file_bytes_read"]),
                    "bytes_read": str(entry["bytes_read"]),
                    "delete_bytes_read": str(entry["delete_bytes_read"]),
                    "data_files_read": str(entry["data_files_read"]),
                    "data_files_skipped": str(entry["data_files_skipped"]),
                    "output_rows": str(entry["output_rows"]),
                    "repetitions_agreeing": str(repetitions),
                }
            )
    return rows, summary


def audit_plans(
    *, raw_dir: Path, repetitions: int, scenarios: list[str]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    plans: list[dict[str, str]] = []
    artifacts: list[dict[str, str]] = []
    for scenario in scenarios:
        for treatment in TREATMENTS:
            digests: dict[str, str] = {}
            for rep in range(1, repetitions + 1):
                path = raw_dir / "plans" / f"rep{rep}-{scenario}-{treatment}.plan"
                if not path.exists():
                    raise ValueError(f"H14 captured no plan at {path}")
                digests[str(rep)] = _sha256(path)
            first = raw_dir / "plans" / f"rep1-{scenario}-{treatment}.plan"
            text = first.read_text(encoding="utf-8")
            body = [line for line in text.splitlines() if line.strip()]
            operators = [line.strip() for line in body if not line.startswith("==")]
            plans.append(
                {
                    "scenario_id": scenario,
                    "treatment_id": treatment,
                    "plan_path": str(first),
                    "plan_sha256": digests["1"],
                    "plan_lines": str(len(body)),
                    "top_operator": operators[0].split(" ")[0] if operators else "",
                    "copy_on_write_rewrite": "yes" if "ReplaceData" in text else "no",
                    "join_operators": ";".join(sorted(set(JOIN_PATTERN.findall(text)))) or "none",
                    "repetitions_agreeing": str(len(set(digests.values()))),
                }
            )
    for kind, pattern in (("plan", "plans/*"), ("session_log", "logs/*"), ("event_log", "eventlogs/*/*")):
        for path in sorted(raw_dir.glob(pattern)):
            if path.is_file():
                artifacts.append(
                    {
                        "kind": kind,
                        "path": str(path),
                        "bytes": str(path.stat().st_size),
                        "sha256": _sha256(path),
                    }
                )
    return plans, artifacts


def build_validation(
    *,
    contract: dict[str, Any],
    environment: dict[str, str],
    read_rows: list[dict[str, str]],
    read_summary: list[dict[str, str]],
    plans: list[dict[str, str]],
    artifacts: list[dict[str, str]],
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
        "every treatment and sweep point yields a measured read size",
        all(int(row["bytes_read"]) > 0 for row in read_summary),
        len(read_summary),
        ";".join(f"{row['scenario_id']}|{row['treatment_id']}={row['bytes_read']}" for row in read_summary),
    )
    add(
        "the read statistics agree between repetitions",
        all(row["repetitions_agreeing"] == str(contract["protocol"]["repetitions"]) for row in read_summary),
        len(read_rows),
        f"{contract['protocol']['repetitions']} repetitions of the same statement over the same state",
    )
    add(
        "the captured plan of a statement is identical between repetitions",
        all(row["repetitions_agreeing"] == "1" for row in plans),
        len(plans),
        ";".join(f"{row['treatment_id']}:{row['plan_sha256'][:8]}" for row in plans),
    )
    add(
        "every preserved artifact carries its size and checksum",
        all(int(row["bytes"]) > 0 and len(row["sha256"]) == 64 for row in artifacts),
        len(artifacts),
        ";".join(
            f"{kind}={sum(1 for row in artifacts if row['kind'] == kind)}"
            for kind in ("plan", "session_log", "event_log")
        ),
    )
    add(
        "the run is declared as instrumented and reports no timing",
        environment.get("instrumentation") == "event_log_enabled;timings_not_reported",
        1,
        f"nproc={environment.get('host_nproc')}, commit {environment.get('git_commit', '')[:7]}",
    )
    return rows


def build_summary(
    *, read_summary: list[dict[str, str]], plans: list[dict[str, str]], artifacts: list[dict[str, str]]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in read_summary:
        rows.append(
            {
                "metric": f"{row['treatment_id'].lower()}_{row['scenario_id']}_bytes_read",
                "value": row["bytes_read"],
                "unit": "bytes",
                "interpretation": (
                    f"{row['iceberg_bytes_read']} from its own table over {row['data_files_read']} data files "
                    f"({row['data_files_skipped']} skipped) and {row['file_bytes_read']} from the staging files, "
                    f"over {row['executions']} executions"
                ),
            }
        )
    for row in plans:
        rows.append(
            {
                "metric": f"plan_{row['treatment_id'].lower()}_{row['scenario_id']}",
                "value": row["top_operator"],
                "unit": "operator",
                "interpretation": (
                    f"copy-on-write rewrite: {row['copy_on_write_rewrite']}; joins: {row['join_operators']}; "
                    f"{row['plan_lines']} plan lines"
                ),
            }
        )
    rows.append(
        {
            "metric": "preserved_artifacts",
            "value": str(len(artifacts)),
            "unit": "files",
            "interpretation": (
                f"{sum(int(row['bytes']) for row in artifacts)} bytes of plans, session logs and event logs"
            ),
        }
    )
    return rows


def run_h14(
    *,
    contract_path: Path,
    raw_dir: Path,
    read_output: Path,
    read_summary_output: Path,
    plan_output: Path,
    artifact_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    environment = read_environment(raw_dir / "environment.txt")
    repetitions = contract["protocol"]["repetitions"]
    scenarios = list(contract["workload"]["scenarios"])
    if environment.get("repetitions") != str(repetitions):
        raise ValueError("the raw run did not use the repetition count the contract states")
    if environment.get("scenarios") != ";".join(scenarios):
        raise ValueError("the raw run did not cover the sweep points the contract states")

    read_rows, read_summary = audit_read_statistics(
        _lines(raw_dir / "read-statistics.txt", "H14R"),
        repetitions=repetitions,
        scenarios=scenarios,
    )
    plans, artifacts = audit_plans(raw_dir=raw_dir, repetitions=repetitions, scenarios=scenarios)
    validation_rows = build_validation(
        contract=contract,
        environment=environment,
        read_rows=read_rows,
        read_summary=read_summary,
        plans=plans,
        artifacts=artifacts,
    )
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["invariant"] for row in validation_rows if row["status"] != "pass"]
        raise ValueError(f"H14 invariants failed: {failed}")
    summary_rows = build_summary(read_summary=read_summary, plans=plans, artifacts=artifacts)

    written = []
    for path, columns, rows in (
        (read_output, READ_COLUMNS, read_rows),
        (read_summary_output, READ_SUMMARY_COLUMNS, read_summary),
        (plan_output, PLAN_COLUMNS, plans),
        (artifact_output, ARTIFACT_COLUMNS, artifacts),
        (validation_output, VALIDATION_COLUMNS, validation_rows),
        (summary_output, SUMMARY_COLUMNS, summary_rows),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    by_key = {(row["scenario_id"], row["treatment_id"]): row for row in read_summary}
    largest = scenarios[-1]
    manifest = {
        "stage": "H14",
        "track": "B",
        "contract_version": contract["contract_version"],
        "collection_status": "collected",
        "environment": environment,
        "read_statistics": {
            f"{row['scenario_id']}|{row['treatment_id']}": {
                "bytes_read": row["bytes_read"],
                "data_files_read": row["data_files_read"],
                "data_files_skipped": row["data_files_skipped"],
            }
            for row in read_summary
        },
        "plans": {
            f"{row['scenario_id']}|{row['treatment_id']}": {
                "top_operator": row["top_operator"],
                "copy_on_write_rewrite": row["copy_on_write_rewrite"],
                "sha256": row["plan_sha256"],
            }
            for row in plans
        },
        "inputs": [_manifest_entry(contract_path)],
        "raw_inputs": [
            _manifest_entry(path)
            for path in sorted(raw_dir.rglob("*"))
            if path.is_file() and path.suffix != ".plan" and "eventlogs" not in path.parts
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
        "scenarios": len(scenarios),
        "executions": len(read_rows),
        "bytes_read": {treatment: by_key[(largest, treatment)]["bytes_read"] for treatment in TREATMENTS},
        "files_read": {treatment: by_key[(largest, treatment)]["data_files_read"] for treatment in TREATMENTS},
        "plans": len(plans),
        "artifacts": len(artifacts),
        "artifact_bytes": sum(int(row["bytes"]) for row in artifacts),
        "status": "collected",
    }
