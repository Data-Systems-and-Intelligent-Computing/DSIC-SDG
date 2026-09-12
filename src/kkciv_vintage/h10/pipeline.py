from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


TREATMENTS = ["B0", "B1", "B2", "B3"]
CLASSES = ["data", "delete", "manifest", "manifest_list", "metadata_json"]
SIZED_CLASSES = {"data", "delete", "manifest"}
REQUIRED_DECISIONS = {
    "h10_catalog_persistence": ("stack", "persist_iceberg_rest_catalog_in_sqlite_volume"),
    "h10_storage_environment": ("measurement", "declare_current_vm_for_storage_and_defer_timing_spec"),
}
LOGICAL_ROWS = {"B0": 14, "B1": 42, "B2": 14, "B3": 52}
FILE_COLUMNS = [
    "repetition",
    "treatment_id",
    "table",
    "object_class",
    "object_path",
    "metadata_size_bytes",
    "object_size_bytes",
    "record_count",
]
FOOTPRINT_COLUMNS = [
    "repetition",
    "treatment_id",
    "table",
    "object_class",
    "objects",
    "bytes",
    "physical_rows",
]
TABLE_COLUMNS = [
    "repetition",
    "treatment_id",
    "table",
    "snapshots",
    "current_rows",
    "reachable_objects",
    "reachable_bytes",
    "location_objects",
    "location_bytes",
    "unreferenced_objects",
    "unreferenced_bytes",
]
SUMMARY_BY_TREATMENT_COLUMNS = [
    "treatment_id",
    "tables",
    "repetitions",
    "total_bytes_min",
    "total_bytes_median",
    "total_bytes_max",
    "data_bytes_median",
    "metadata_bytes_median",
    "data_files_median",
    "physical_rows",
    "logical_rows",
    "retained_snapshots",
    "bytes_identical_across_repetitions",
]
RECALL_COLUMNS = [
    "treatment_id",
    "requested_observation_id",
    "requested_value_lexeme",
    "returned_observation_id",
    "returned_value_lexeme",
    "locator",
    "addressable",
    "expected_addressable",
    "exact_match",
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
        raise ValueError(f"H10 requires a valid {manifest_path} input")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested output {path}")
        if "rows" in item and len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested output {path}")
        outputs[path.name] = (path, item)
    return outputs


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h10a.1"
        or contract.get("stage") != "H10"
        or contract.get("track") != "A"
    ):
        raise ValueError("unsupported H10A contract")
    if contract["human_decisions"]["decision_ids"] != list(REQUIRED_DECISIONS):
        raise ValueError("H10A human decisions do not match the approved registry")
    if list(contract["tables"]) != TREATMENTS:
        raise ValueError("H10A must measure B0 B1 B2 and B3")
    protocol = contract["protocol"]
    if protocol["repetitions"] < 3 or set(protocol["expected_markers"]) != set(TREATMENTS):
        raise ValueError("H10A requires at least three repetitions and a marker per treatment")
    footprint = contract["footprint"]
    if footprint["classes"] != CLASSES or set(footprint["metadata_size_must_match_object_size"]) != SIZED_CLASSES:
        raise ValueError("H10A footprint classes do not match the implementation")
    recall = contract["recall_after_restart"]
    if recall["requests_per_treatment"] != 38 or recall["expected_addressable"] != {"B0": 14, "B1": 38, "B2": 14, "B3": 38}:
        raise ValueError("H10A recall expectations changed")
    boundary = contract["measurement_boundary"]
    if boundary["timing"] != "not_measured":
        raise ValueError("H10A must not measure or claim runtime")


def validate_human_decisions(rows: list[dict[str, str]]) -> None:
    by_id = {row["decision_id"]: row for row in rows}
    if len(by_id) != len(rows) or not set(REQUIRED_DECISIONS) <= set(by_id):
        raise ValueError("H10A requires the two H10 measurement decisions in the registry")
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
            raise ValueError(f"H10 human decision {decision_id} is not approved as recorded")
    # Later H10 answers (audit responses, H10B inputs) may extend the registry; they
    # never relax the two decisions the measurement itself depended on.
    for row in rows:
        if row["decision_id"] in REQUIRED_DECISIONS:
            continue
        if row["decided_by"] != "human_reviewer" or row["status"] != "approved" or not row["rationale"]:
            raise ValueError(f"H10 registry row {row['decision_id']} is not an approved human decision")


def read_environment(path: Path) -> dict[str, str]:
    environment = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        environment[key] = value
    return environment


def measure_footprint(
    *,
    contract: dict[str, Any],
    footprint_lines: list[list[str]],
    state_lines: list[list[str]],
    listing_lines: list[list[str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    expected_tables = {(treatment, table) for treatment, tables in contract["tables"].items() for table in tables}
    repetitions = [str(rep) for rep in range(1, contract["protocol"]["repetitions"] + 1)]
    listing: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for _, rep, treatment, table, path, size in listing_lines:
        listing[(rep, table)][path] = int(size)
    states = {(rep, table): (snapshots, rows) for _, rep, _, table, snapshots, rows in state_lines}

    file_rows: list[dict[str, str]] = []
    referenced: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for _, rep, treatment, table, object_class, path, metadata_size, records in footprint_lines:
        if (treatment, table) not in expected_tables or rep not in repetitions or object_class not in CLASSES:
            raise ValueError(f"unexpected H10 footprint row for {treatment} {table} rep {rep}")
        if path in referenced[(rep, table, object_class)]:
            continue
        objects = listing[(rep, table)]
        if path not in objects:
            raise ValueError(f"metadata references a missing object {path}")
        if object_class in SIZED_CLASSES and int(metadata_size) != objects[path]:
            raise ValueError(f"metadata size differs from the MinIO object size for {path}")
        referenced[(rep, table, object_class)].add(path)
        file_rows.append(
            {
                "repetition": rep,
                "treatment_id": treatment,
                "table": table,
                "object_class": object_class,
                "object_path": path,
                "metadata_size_bytes": metadata_size,
                "object_size_bytes": str(objects[path]),
                "record_count": records,
            }
        )

    footprint_rows: list[dict[str, str]] = []
    table_rows: list[dict[str, str]] = []
    for rep in repetitions:
        for treatment, table in sorted(expected_tables, key=lambda item: (TREATMENTS.index(item[0]), item[1])):
            if (rep, table) not in states:
                raise ValueError(f"H10 has no state row for {table} rep {rep}")
            rows_here = [row for row in file_rows if row["repetition"] == rep and row["table"] == table]
            for object_class in CLASSES:
                in_class = [row for row in rows_here if row["object_class"] == object_class]
                footprint_rows.append(
                    {
                        "repetition": rep,
                        "treatment_id": treatment,
                        "table": table,
                        "object_class": object_class,
                        "objects": str(len(in_class)),
                        "bytes": str(sum(int(row["object_size_bytes"]) for row in in_class)),
                        "physical_rows": str(sum(int(row["record_count"] or 0) for row in in_class)) if object_class in {"data", "delete"} else "",
                    }
                )
            if not any(row["object_class"] == "metadata_json" for row in rows_here) or not any(
                row["object_class"] == "manifest_list" for row in rows_here
            ):
                raise ValueError(f"H10 {table} rep {rep} lacks metadata or manifest-list objects")
            reachable_paths = {row["object_path"] for row in rows_here}
            location = listing[(rep, table)]
            unreferenced = {path: size for path, size in location.items() if path not in reachable_paths}
            table_rows.append(
                {
                    "repetition": rep,
                    "treatment_id": treatment,
                    "table": table,
                    "snapshots": states[(rep, table)][0],
                    "current_rows": states[(rep, table)][1],
                    "reachable_objects": str(len(reachable_paths)),
                    "reachable_bytes": str(sum(int(row["object_size_bytes"]) for row in rows_here)),
                    "location_objects": str(len(location)),
                    "location_bytes": str(sum(location.values())),
                    "unreferenced_objects": str(len(unreferenced)),
                    "unreferenced_bytes": str(sum(unreferenced.values())),
                }
            )

    summary_rows: list[dict[str, str]] = []
    for treatment in TREATMENTS:
        per_rep_total: list[int] = []
        per_rep_data: list[int] = []
        per_rep_metadata: list[int] = []
        per_rep_files: list[int] = []
        physical_rows: set[str] = set()
        snapshots: set[str] = set()
        for rep in repetitions:
            rows_here = [row for row in footprint_rows if row["repetition"] == rep and row["treatment_id"] == treatment]
            per_rep_total.append(sum(int(row["bytes"]) for row in rows_here))
            per_rep_data.append(sum(int(row["bytes"]) for row in rows_here if row["object_class"] in {"data", "delete"}))
            per_rep_metadata.append(sum(int(row["bytes"]) for row in rows_here if row["object_class"] not in {"data", "delete"}))
            per_rep_files.append(sum(int(row["objects"]) for row in rows_here if row["object_class"] == "data"))
            physical_rows.add(str(sum(int(row["physical_rows"] or 0) for row in rows_here)))
            snapshots.add(
                "+".join(
                    row["snapshots"]
                    for row in table_rows
                    if row["repetition"] == rep and row["treatment_id"] == treatment
                )
            )
        if len(physical_rows) != 1 or len(snapshots) != 1:
            raise ValueError(f"H10 {treatment} physical rows or snapshots differ across repetitions")
        summary_rows.append(
            {
                "treatment_id": treatment,
                "tables": ";".join(contract["tables"][treatment]),
                "repetitions": str(len(repetitions)),
                "total_bytes_min": str(min(per_rep_total)),
                "total_bytes_median": str(int(statistics.median(per_rep_total))),
                "total_bytes_max": str(max(per_rep_total)),
                "data_bytes_median": str(int(statistics.median(per_rep_data))),
                "metadata_bytes_median": str(int(statistics.median(per_rep_metadata))),
                "data_files_median": str(int(statistics.median(per_rep_files))),
                "physical_rows": physical_rows.pop(),
                "logical_rows": str(LOGICAL_ROWS[treatment]),
                "retained_snapshots": snapshots.pop(),
                "bytes_identical_across_repetitions": "yes" if len(set(per_rep_total)) == 1 else "no",
            }
        )
    return file_rows, footprint_rows, table_rows, summary_rows


def audit_recall(
    *,
    recall_lines: list[list[str]],
    observations: list[dict[str, str]],
    h9c_audit: list[dict[str, str]],
    b1_reproducibility: list[dict[str, str]],
    contract: dict[str, Any],
) -> list[dict[str, str]]:
    requested = {row["observation_id"]: row for row in observations}
    expected = {
        (row["treatment_id"], row["requested_observation_id"]): row["computed_addressable"] == "yes"
        for row in h9c_audit
    }
    b1_orders = {row["requested_observation_id"]: row["matching_snapshot_orders"] for row in b1_reproducibility}
    rows: list[dict[str, str]] = []
    seen = set()
    for _, treatment, request_id, returned_id, returned_lexeme, locator in recall_lines:
        if (treatment, request_id) in seen or request_id not in requested:
            raise ValueError(f"H10 recall row for {treatment} {request_id} is duplicated or unknown")
        seen.add((treatment, request_id))
        addressable = returned_id == request_id
        exact = addressable and returned_lexeme == requested[request_id]["value_lexeme"]
        if treatment == "B1" and addressable and locator != f"snapshot_orders={b1_orders[request_id]}":
            raise ValueError(f"H10 B1 recall of {request_id} came from unexpected snapshots {locator}")
        if returned_id and not addressable:
            raise ValueError(f"H10 {treatment} returned a different observation for {request_id}")
        if addressable and not exact:
            raise ValueError(f"H10 {treatment} returned a different value for {request_id}")
        if addressable != expected[(treatment, request_id)]:
            raise ValueError(f"H10 {treatment} recall of {request_id} disagrees with the H9C audit")
        rows.append(
            {
                "treatment_id": treatment,
                "requested_observation_id": request_id,
                "requested_value_lexeme": requested[request_id]["value_lexeme"],
                "returned_observation_id": returned_id,
                "returned_value_lexeme": returned_lexeme,
                "locator": locator if addressable else "",
                "addressable": "yes" if addressable else "no",
                "expected_addressable": "yes" if expected[(treatment, request_id)] else "no",
                "exact_match": "yes" if exact else "not_applicable",
            }
        )
    if seen != {(treatment, request_id) for treatment in TREATMENTS for request_id in requested}:
        raise ValueError("H10 recall does not cover 38 requests for every treatment")
    counts = {treatment: sum(row["addressable"] == "yes" for row in rows if row["treatment_id"] == treatment) for treatment in TREATMENTS}
    if counts != contract["recall_after_restart"]["expected_addressable"]:
        raise ValueError(f"H10 recall counts {counts} differ from the contract")
    rows.sort(key=lambda row: (TREATMENTS.index(row["treatment_id"]), row["requested_observation_id"]))
    return rows


def run_h10(
    *,
    contract_path: Path,
    decisions_path: Path,
    raw_dir: Path,
    h6_manifest_path: Path,
    b1_manifest_path: Path,
    h9c_manifest_path: Path,
    files_output: Path,
    footprint_output: Path,
    tables_output: Path,
    treatment_summary_output: Path,
    recall_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    decisions = _read_csv(decisions_path)
    validate_human_decisions(decisions)

    environment = read_environment(raw_dir / "environment.txt")
    if not environment.get("catalog_uri", "").startswith(contract["protocol"]["catalog_uri_prefix"]):
        raise ValueError("H10 measurement ran without the persistent catalog")
    if environment.get("git_dirty_entries") != "0":
        raise ValueError("H10 measurement started from a dirty working tree")
    if environment.get("repetitions") != str(contract["protocol"]["repetitions"]):
        raise ValueError("H10 raw run used a different repetition count")

    markers = [line.split("|", 2) for line in (raw_dir / "apply-markers.txt").read_text(encoding="utf-8").splitlines()]
    expected_markers = contract["protocol"]["expected_markers"]
    for rep, treatment, marker in markers:
        if marker != expected_markers[treatment]:
            raise ValueError(f"H10 rep {rep} {treatment} marker {marker} differs from the recorded marker")
    if len(markers) != contract["protocol"]["repetitions"] * len(TREATMENTS):
        raise ValueError("H10 apply markers are incomplete")

    file_rows, footprint_rows, table_rows, treatment_rows = measure_footprint(
        contract=contract,
        footprint_lines=_lines(raw_dir / "footprint.txt", "H10F"),
        state_lines=_lines(raw_dir / "footprint.txt", "H10S"),
        listing_lines=_lines(raw_dir / "listing.txt", "H10L"),
    )

    h6 = _manifest_outputs(h6_manifest_path, {"stage": "H6", "schema_status": "validated"})
    b1 = _manifest_outputs(b1_manifest_path, {"stage": "H8", "track": "A", "treatment_id": "B1", "implementation_status": "implemented"})
    h9c = _manifest_outputs(h9c_manifest_path, {"stage": "H9", "track": "C", "evidence_status": "validated"})
    snapshot_counts = _lines(raw_dir / "recall.txt", "H10SNAPCOUNT")
    if snapshot_counts != [["H10SNAPCOUNT", "3"]]:
        raise ValueError("H10 B1 must keep three snapshots after the catalog restart")
    recall_rows = audit_recall(
        recall_lines=_lines(raw_dir / "recall.txt", "H10R"),
        observations=_read_csv(h6["h6-indicator-observations.csv"][0]),
        h9c_audit=_read_csv(h9c["h9c-reproducibility-audit.csv"][0]),
        b1_reproducibility=_read_csv(b1["h8-b1-reproducibility.csv"][0]),
        contract=contract,
    )

    by_treatment = {row["treatment_id"]: row for row in treatment_rows}
    unreferenced = sum(int(row["unreferenced_bytes"]) for row in table_rows if row["repetition"] == str(contract["protocol"]["repetitions"]))
    recalled = {treatment: sum(row["addressable"] == "yes" for row in recall_rows if row["treatment_id"] == treatment) for treatment in TREATMENTS}
    validation = [
        {"invariant": "h10a_contract", "status": "passed", "checked_rows": "6", "detail": "decisions tables protocol footprint recall and boundary match h10a.1"},
        {"invariant": "human_decisions", "status": "passed", "checked_rows": str(len(decisions)), "detail": "persistent catalog and declared storage environment approved on 2026-09-11; later H10 audit answers extend the same registry"},
        {"invariant": "persistent_catalog", "status": "passed", "checked_rows": "1", "detail": environment["catalog_uri"]},
        {"invariant": "clean_start", "status": "passed", "checked_rows": "1", "detail": f"git commit {environment['git_commit']} with no local changes"},
        {"invariant": "recorded_markers", "status": "passed", "checked_rows": str(len(markers)), "detail": "every repetition reproduces the recorded B0 B1 B2 and B3 verification markers"},
        {"invariant": "objects_exist_with_metadata_size", "status": "passed", "checked_rows": str(len(file_rows)), "detail": "every referenced object exists in MinIO; data delete and manifest sizes equal their metadata"},
        {"invariant": "unreferenced_excluded", "status": "passed", "checked_rows": str(len(table_rows)), "detail": f"{unreferenced} unreferenced bytes in the final table locations are reported and excluded"},
        {"invariant": "stable_physical_layout", "status": "passed", "checked_rows": str(len(treatment_rows)), "detail": "physical rows and retained snapshots are identical across repetitions"},
        {"invariant": "recall_after_restart", "status": "passed", "checked_rows": str(len(recall_rows)), "detail": "B0=%d B1=%d B2=%d B3=%d requests recalled exactly after the catalog restart" % tuple(recalled[t] for t in TREATMENTS)},
        {"invariant": "no_timing_claim", "status": "passed", "checked_rows": "0", "detail": "no runtime is measured; bytes are reported for the declared environment"},
    ]
    summary = [
        {"metric": "repetitions", "value": str(contract["protocol"]["repetitions"]), "unit": "runs", "interpretation": "serial purge-rebuild-measure cycles"},
        {"metric": "host_nproc", "value": environment["host_nproc"], "unit": "vCPU", "interpretation": "declared environment, not the proposal specification"},
        {"metric": "host_mem_total_bytes", "value": environment["host_mem_total_bytes"], "unit": "bytes", "interpretation": "declared environment"},
    ]
    for treatment in TREATMENTS:
        row = by_treatment[treatment]
        summary.append(
            {
                "metric": f"{treatment.lower()}_reachable_bytes_median",
                "value": row["total_bytes_median"],
                "unit": "bytes",
                "interpretation": f"range {row['total_bytes_min']}-{row['total_bytes_max']}; data {row['data_bytes_median']}; metadata {row['metadata_bytes_median']}; physical rows {row['physical_rows']}",
            }
        )
    for treatment in TREATMENTS:
        summary.append(
            {
                "metric": f"{treatment.lower()}_recalled_after_restart",
                "value": str(recalled[treatment]),
                "unit": "requests",
                "interpretation": "exact observation and lexeme after restarting the persistent catalog",
            }
        )
    summary.append({"metric": "timed_runs", "value": "0", "unit": "runs", "interpretation": "timing waits for the VM decision before H10B/H11"})

    written_outputs = []
    for path, columns, rows in (
        (files_output, FILE_COLUMNS, file_rows),
        (footprint_output, FOOTPRINT_COLUMNS, footprint_rows),
        (tables_output, TABLE_COLUMNS, table_rows),
        (treatment_summary_output, SUMMARY_BY_TREATMENT_COLUMNS, treatment_rows),
        (recall_output, RECALL_COLUMNS, recall_rows),
        (validation_output, VALIDATION_COLUMNS, validation),
        (summary_output, SUMMARY_COLUMNS, summary),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )
    raw_files = sorted(path for path in raw_dir.iterdir() if path.is_file())
    manifest = {
        "stage": "H10",
        "track": "A",
        "contract_version": contract["contract_version"],
        "measurement_status": "measured",
        "environment": environment,
        "storage": {row["treatment_id"]: {key: row[key] for key in SUMMARY_BY_TREATMENT_COLUMNS if key != "treatment_id"} for row in treatment_rows},
        "recall_after_restart": recalled,
        "measurement": contract["measurement_boundary"],
        "raw_inputs": [{"path": str(path), "sha256": _sha256(path)} for path in raw_files],
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)}
            for path in (contract_path, decisions_path, h6_manifest_path, b1_manifest_path, h9c_manifest_path)
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "repetitions": contract["protocol"]["repetitions"],
        "objects": len(file_rows),
        **{f"{t.lower()}_bytes": int(by_treatment[t]["total_bytes_median"]) for t in TREATMENTS},
        **{f"{t.lower()}_recalled": recalled[t] for t in TREATMENTS},
        "stable": all(row["bytes_identical_across_repetitions"] == "yes" for row in treatment_rows),
        "status": "measured",
    }
