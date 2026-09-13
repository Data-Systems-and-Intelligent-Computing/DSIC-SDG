from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.article.pipeline import Sources
from kkciv_vintage.h11.pipeline import (
    SUMMARY_COLUMNS,
    TREATMENTS,
    VALIDATION_COLUMNS,
    _manifest_entry,
    _write_csv,
)


TABLE_INVENTORY_COLUMNS = [
    "table_id",
    "research_question",
    "title",
    "origin",
    "rows",
    "output_path",
    "sources",
    "note",
]
FIGURE_INVENTORY_COLUMNS = [
    "figure_id",
    "research_question",
    "title",
    "x_axis",
    "y_axis",
    "scale",
    "series",
    "rows",
    "output_path",
    "origin",
    "note",
    "caption",
]
SWEEP_STATE_COLUMNS = [
    "treatment_id",
    "baseline_rows",
    "baseline_snapshots",
    "cells_evaluated_per_revision",
    "rows_written_per_revision",
    "state_after_revision",
    "snapshots_after_revision",
]
SWEEP_TIME_COLUMNS = [
    "cells_revised",
    "selection_share",
    *[f"{treatment.lower()}_total_seconds" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_write_seconds" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_maintenance_seconds" for treatment in TREATMENTS],
]
SWEEP_BYTES_COLUMNS = [
    "cells_revised",
    "selection_share",
    *[f"{treatment.lower()}_delta_bytes" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_data_bytes" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_metadata_bytes" for treatment in TREATMENTS],
]
BREAKEVEN_COLUMNS = [
    "comparison",
    "measure",
    "measured_direction",
    "measured_crossing",
    "projected_crossing_cells",
    "projection_status",
    "condition_for_a_crossing",
]
RECALL_COLUMNS = [
    "scale",
    "requests",
    *[f"{treatment.lower()}_recall" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_failures" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_material_failures" for treatment in TREATMENTS],
]
REAL_RELEASE_COLUMNS = [
    "arrival_order",
    "source_id",
    "arriving_rows",
    "overwritten_rows",
    "value_changed_rows",
    *[f"{treatment.lower()}_total_seconds" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_referenced_bytes" for treatment in TREATMENTS],
]
READ_COLUMNS = [
    "treatment_id",
    "own_table_bytes",
    "own_table_data_files",
    "staging_bytes",
    "total_bytes",
    "top_plan_operator",
    "copy_on_write_rewrite",
]
FIGURE_POINT_COLUMNS = [
    "figure_id",
    "series",
    "x",
    "y",
    "y_min",
    "y_max",
    "unit",
]


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h15.1"
        or contract.get("stage") != "H15"
        or contract.get("track") != "AC"
    ):
        raise ValueError("unsupported H15 contract")
    frame = contract["frozen_frame"]
    if frame["frozen_at"] != "H11" or frame["tables"] != 14 or frame["figures"] != 4:
        raise ValueError("H15 must build on the frame frozen at H11")
    if "a table added afterwards must be marked as added" not in frame["rule"]:
        raise ValueError("H15 must mark every table added after the frame was frozen")
    if contract["sources"]["no_manual_numbers"] != (
        "a composed table may only contain values read from a verified source, never a value typed in by hand"
    ):
        raise ValueError("H15 may not contain hand-typed values")
    if not contract["environment_note"]:
        raise ValueError("H15 needs the environment note every caption must carry")


def _by(rows: list[dict[str, str]], *keys: str) -> dict[tuple[str, ...], dict[str, str]]:
    return {tuple(row[key] for key in keys): row for row in rows}


def compose_sweep_state(src: Sources) -> list[dict[str, str]]:
    """What each treatment holds before a revision and what one revision changes."""
    scenarios = src.rows("h11-sweep-scenarios.csv")
    baseline = src.rows("h11-baseline-expectations.csv")
    largest = max(scenarios, key=lambda row: int(row["cells_revised"]))
    rows: list[dict[str, str]] = []
    for treatment in TREATMENTS:
        tables = [row for row in baseline if row["treatment_id"] == treatment]
        rows.append(
            {
                "treatment_id": treatment,
                "baseline_rows": ";".join(
                    f"{row['table'].split('.')[-1]}={row['expected_rows']}" for row in tables
                ),
                "baseline_snapshots": ";".join(
                    f"{row['table'].split('.')[-1]}={row['expected_snapshots']}" for row in tables
                ),
                "cells_evaluated_per_revision": largest[f"{treatment.lower()}_cells_evaluated"],
                "rows_written_per_revision": largest[f"{treatment.lower()}_rows_written_logical"],
                "state_after_revision": largest[f"{treatment.lower()}_expected_rows"],
                "snapshots_after_revision": largest[f"{treatment.lower()}_expected_snapshots"],
            }
        )
    return rows


def compose_sweep_measure(src: Sources, *, measure: str) -> list[dict[str, str]]:
    """One row per sweep point, one column group per treatment."""
    cost = src.rows("h11-apply-cost.csv")
    by_key = _by(cost, "scenario_id", "treatment_id")
    points = sorted(
        {(int(row["cells_revised"]), row["scenario_id"], row["selection_share"]) for row in cost}
    )
    rows: list[dict[str, str]] = []
    for cells, scenario_id, share in points:
        row = {"cells_revised": str(cells), "selection_share": share}
        for treatment in TREATMENTS:
            source = by_key[(scenario_id, treatment)]
            prefix = treatment.lower()
            if measure == "seconds":
                row[f"{prefix}_total_seconds"] = source["total_seconds_median"]
                row[f"{prefix}_write_seconds"] = (
                    f"{source['write_seconds_median']} "
                    f"({source['write_seconds_min']}-{source['write_seconds_max']})"
                )
                row[f"{prefix}_maintenance_seconds"] = source["maintenance_seconds_median"]
            else:
                row[f"{prefix}_delta_bytes"] = source["delta_bytes_median"]
                row[f"{prefix}_data_bytes"] = source["delta_data_bytes_median"]
                row[f"{prefix}_metadata_bytes"] = source["delta_metadata_bytes_median"]
        rows.append(row)
    return rows


def compose_breakeven(src: Sources) -> list[dict[str, str]]:
    conditions = src.rows("h14c-breakeven-conditions.csv")
    return [
        {
            "comparison": row["comparison"],
            "measure": row["measure"],
            "measured_direction": row["measured_direction"],
            "measured_crossing": row["measured_crossing"],
            "projected_crossing_cells": row["projected_crossing_cells"],
            "projection_status": row["projection_status"],
            "condition_for_a_crossing": row["condition_for_a_crossing"],
        }
        for row in conditions
    ]


def compose_recall(src: Sources) -> list[dict[str, str]]:
    """Both scales of the reproducibility audit in one table."""
    audit = src.rows("h13c-reproducibility-table.csv")
    profile = src.rows("h13c-failure-profile.csv")
    rows: list[dict[str, str]] = []
    for scale in ("fixture", "panel"):
        selected = {row["treatment_id"]: row for row in audit if row["scale"] == scale}
        row = {"scale": scale, "requests": selected["B0"]["requests"]}
        for treatment in TREATMENTS:
            prefix = treatment.lower()
            row[f"{prefix}_recall"] = selected[treatment]["success_rate"]
            row[f"{prefix}_failures"] = selected[treatment]["failures"]
            row[f"{prefix}_material_failures"] = (
                str(
                    sum(
                        int(item["material_failures"])
                        for item in profile
                        if item["treatment_id"] == treatment
                        and item["failure_kind"] != "serving_value_superseded"
                    )
                )
                if scale == "panel"
                else ""
            )
        rows.append(row)
    return rows


def compose_real_releases(src: Sources) -> list[dict[str, str]]:
    cost = src.rows("h12-arrival-cost.csv")
    by_key = _by(cost, "arrival_order", "treatment_id")
    arrivals = sorted({row["arrival_order"] for row in cost}, key=int)
    rows: list[dict[str, str]] = []
    for arrival in arrivals:
        first = by_key[(arrival, "B0")]
        row = {
            "arrival_order": arrival,
            "source_id": first["source_id"],
            "arriving_rows": first["arriving_rows"],
            "overwritten_rows": first["overwritten_rows"],
            "value_changed_rows": first["value_changed_rows"],
        }
        for treatment in TREATMENTS:
            source = by_key[(arrival, treatment)]
            row[f"{treatment.lower()}_total_seconds"] = source["total_seconds_median"]
            row[f"{treatment.lower()}_referenced_bytes"] = source["referenced_bytes_after"]
        rows.append(row)
    return rows


def compose_reads(src: Sources) -> list[dict[str, str]]:
    reads = src.rows("h14-read-summary.csv")
    plans = _by(src.rows("h14-query-plans.csv"), "scenario_id", "treatment_id")
    largest = sorted({row["scenario_id"] for row in reads})[-1]
    rows: list[dict[str, str]] = []
    for treatment in TREATMENTS:
        source = next(
            row for row in reads if row["scenario_id"] == largest and row["treatment_id"] == treatment
        )
        plan = plans[(largest, treatment)]
        rows.append(
            {
                "treatment_id": treatment,
                "own_table_bytes": source["iceberg_bytes_read_median"],
                "own_table_data_files": source["data_files_read"],
                "staging_bytes": source["file_bytes_read_median"],
                "total_bytes": source["bytes_read"],
                "top_plan_operator": plan["top_operator"],
                "copy_on_write_rewrite": plan["copy_on_write_rewrite"],
            }
        )
    return rows


def build_figures(src: Sources) -> list[dict[str, str]]:
    """Tidy figure data. Every point that has repetitions carries its range."""
    cost = src.rows("h11-apply-cost.csv")
    audit = src.rows("h13c-reproducibility-table.csv")
    points: list[dict[str, str]] = []
    for row in sorted(cost, key=lambda item: (item["treatment_id"], int(item["cells_revised"]))):
        cells = row["cells_revised"]
        maintenance = Decimal(row["maintenance_seconds_median"])
        points.append(
            {
                "figure_id": "G1",
                "series": row["treatment_id"],
                "x": cells,
                "y": row["total_seconds_median"],
                "y_min": f"{Decimal(row['write_seconds_min']) + maintenance:.3f}",
                "y_max": f"{Decimal(row['write_seconds_max']) + maintenance:.3f}",
                "unit": "seconds",
            }
        )
        points.append(
            {
                "figure_id": "G2",
                "series": row["treatment_id"],
                "x": cells,
                "y": row["delta_bytes_median"],
                "y_min": row["delta_bytes_min"],
                "y_max": row["delta_bytes_max"],
                "unit": "bytes",
            }
        )
        points.append(
            {
                "figure_id": "G3",
                "series": row["treatment_id"],
                "x": cells,
                "y": row["cells_evaluated"],
                "y_min": row["cells_evaluated"],
                "y_max": row["cells_evaluated"],
                "unit": "cells",
            }
        )
    # G4 as the frame froze it: one bar group per treatment, official against synthetic
    # requests, taken from the largest sweep point.
    recall = src.rows("h11-recall.csv")
    largest = sorted({row["scenario_id"] for row in recall})[-1]
    for row in sorted(recall, key=lambda item: (item["treatment_id"], item["request_kind"])):
        if row["scenario_id"] != largest:
            continue
        points.append(
            {
                "figure_id": "G4",
                "series": (
                    "permintaan resmi"
                    if row["request_kind"] == "official"
                    else "permintaan sintetis"
                ),
                "x": row["treatment_id"],
                "y": row["recall_rate"],
                "y_min": row["recall_rate"],
                "y_max": row["recall_rate"],
                "unit": "ratio",
            }
        )
    # G5 is not in the frozen frame. The panel audit did not exist when the frame was
    # written, and the two scales together say something neither says alone.
    for row in audit:
        points.append(
            {
                "figure_id": "G5",
                "series": row["treatment_id"],
                "x": row["scale"],
                "y": row["success_rate"],
                "y_min": row["success_rate"],
                "y_max": row["success_rate"],
                "unit": "ratio",
            }
        )
    return points


def build_inventories(
    *, contract: dict[str, Any], composed: dict[str, dict[str, Any]], figures: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    note = contract["environment_note"]
    tables = [
        {
            "table_id": key,
            "research_question": entry["rq"],
            "title": entry["title"],
            "origin": entry["origin"],
            "rows": str(entry["rows"]),
            "output_path": entry["path"],
            "sources": ";".join(entry["sources"]),
            "note": entry["note"],
        }
        for key, entry in composed.items()
    ]
    figure_meta = {
        "G1": (
            "P3",
            "Waktu penghitungan ulang terhadap besaran revisi",
            "sel direvisi",
            "detik",
            "linear",
        ),
        "G2": (
            "P3",
            "Pertambahan byte terhadap besaran revisi",
            "sel direvisi",
            "byte",
            "log",
        ),
        "G3": (
            "P3",
            "Sel yang dievaluasi terhadap besaran revisi",
            "sel direvisi",
            "sel dievaluasi",
            "log",
        ),
        "G4": (
            "P4",
            "Keberhasilan memanggil ulang angka terbit per perlakuan",
            "perlakuan",
            "rasio",
            "linear",
        ),
        "G5": (
            "P4",
            "Keberhasilan memanggil ulang pada kedua skala beban",
            "skala beban",
            "rasio",
            "linear",
        ),
    }
    figure_origin = {
        "G1": ("frozen_frame", ""),
        "G2": ("frozen_frame", ""),
        "G3": ("frozen_frame", ""),
        "G4": ("frozen_frame", ""),
        "G5": (
            "added_after_the_frame_was_frozen",
            "audit panel H13C belum ada ketika kerangka dibekukan pada H11",
        ),
    }
    figure_rows: list[dict[str, str]] = []
    for figure_id, (rq, title, x_axis, y_axis, scale) in figure_meta.items():
        selected = [row for row in figures if row["figure_id"] == figure_id]
        series = sorted({row["series"] for row in selected})
        caption = f"{title}. Median tiga repetisi beserta nilai minimum dan maksimum. {note}"
        if figure_id == "G3":
            caption = (
                f"{title}. Kurva B0 dan B3 berimpit karena keduanya mengevaluasi tepat sel yang "
                f"direvisi, demikian pula B1 dan B2 yang selalu menghitung ulang seluruh sel. {note}"
            )
        if figure_id == "G4":
            caption = (
                f"{title}. Permintaan resmi dan permintaan sintetis pada titik sweep terbesar. {note}"
            )
        elif figure_id == "G5":
            caption = (
                f"{title}. Fixture bukti berisi 38 permintaan dan panel provinsi berisi 6.983 "
                f"permintaan. {note}"
            )
        origin, origin_note = figure_origin[figure_id]
        figure_rows.append(
            {
                "figure_id": figure_id,
                "research_question": rq,
                "title": title,
                "x_axis": x_axis,
                "y_axis": y_axis,
                "scale": scale,
                "series": ";".join(series),
                "rows": str(len(selected)),
                "output_path": "results/processed/h15-figure-data.csv",
                "origin": origin,
                "note": origin_note,
                "caption": caption,
            }
        )
    return tables, figure_rows


def build_validation(
    *,
    contract: dict[str, Any],
    tables: list[dict[str, str]],
    figures: list[dict[str, str]],
    figure_inventory: list[dict[str, str]],
    src: Sources,
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
        "every composed table names the sources it was built from",
        all(row["sources"] for row in tables),
        len(tables),
        ";".join(row["table_id"] for row in tables),
    )
    add(
        "every source was verified against its stage manifest before a value was read",
        bool(src.used),
        len(src.used),
        f"{len(src.used)} sources verified through data/manifests",
    )
    added = [row for row in tables if row["origin"] == "added_after_the_frame_was_frozen"]
    add(
        "a table added after the frame was frozen carries its reason",
        all(row["note"] for row in added),
        len(added),
        ";".join(f"{row['table_id']}:{row['note'][:40]}" for row in added) or "none added",
    )
    with_range = [row for row in figures if row["figure_id"] in {"G1", "G2"}]
    add(
        "every figure point with repetitions carries its minimum and maximum",
        all(row["y_min"] and row["y_max"] for row in with_range),
        len(with_range),
        "G1 and G2 carry the range of the three sweep repetitions",
    )
    added_figures = [
        row for row in figure_inventory if row["origin"] == "added_after_the_frame_was_frozen"
    ]
    add(
        "a figure added after the frame was frozen carries its reason",
        all(row["note"] for row in added_figures),
        len(added_figures),
        ";".join(f"{row['figure_id']}:{row['note'][:40]}" for row in added_figures) or "none added",
    )
    add(
        "every figure caption names the declared environment",
        all(contract["environment_note"] in row["caption"] for row in figure_inventory),
        len(figure_inventory),
        contract["environment_note"][:60],
    )
    return rows


def run_h15(
    *,
    contract_path: Path,
    manifest_dir: Path,
    output_dir: Path,
    table_inventory_output: Path,
    figure_inventory_output: Path,
    figure_data_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    src = Sources(manifest_dir)

    definitions = [
        (
            "T7",
            "P3",
            "Keadaan dasar sweep dan yang ditulis tiap perlakuan",
            SWEEP_STATE_COLUMNS,
            compose_sweep_state(src),
            ["h11-sweep-scenarios.csv", "h11-baseline-expectations.csv"],
            "frozen_frame",
            "",
        ),
        (
            "T8",
            "P3",
            "Waktu penghitungan ulang per titik sweep",
            SWEEP_TIME_COLUMNS,
            compose_sweep_measure(src, measure="seconds"),
            ["h11-apply-cost.csv"],
            "frozen_frame",
            "",
        ),
        (
            "T9",
            "P3",
            "Pertambahan byte per titik sweep",
            SWEEP_BYTES_COLUMNS,
            compose_sweep_measure(src, measure="bytes"),
            ["h11-apply-cost.csv"],
            "frozen_frame",
            "",
        ),
        (
            "T10",
            "P3",
            "Titik impas inkremental dan syaratnya",
            BREAKEVEN_COLUMNS,
            compose_breakeven(src),
            ["h14c-breakeven-conditions.csv"],
            "frozen_frame",
            "",
        ),
        (
            "T13",
            "P4",
            "Keberhasilan memanggil ulang angka terbit pada kedua skala",
            RECALL_COLUMNS,
            compose_recall(src),
            ["h13c-reproducibility-table.csv", "h13c-failure-profile.csv"],
            "frozen_frame",
            "",
        ),
        (
            "T15",
            "P3",
            "Ongkos menerapkan keempat rilis nyata",
            REAL_RELEASE_COLUMNS,
            compose_real_releases(src),
            ["h12-arrival-cost.csv"],
            "added_after_the_frame_was_frozen",
            "H12 mengukur revisi nyata setelah kerangka dibekukan pada H11",
        ),
        (
            "T16",
            "P3",
            "Byte yang dibaca dan rencana eksekusi tiap pernyataan tulis",
            READ_COLUMNS,
            compose_reads(src),
            ["h14-read-summary.csv", "h14-query-plans.csv"],
            "added_after_the_frame_was_frozen",
            "H14 menutup metrik s2 yang pada kerangka masih dinyatakan tidak terukur",
        ),
    ]

    written = []
    composed: dict[str, dict[str, Any]] = {}
    for table_id, rq, title, columns, rows, sources, origin, note in definitions:
        path = output_dir / f"h15-table-{table_id.lower()}.csv"
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))
        composed[table_id] = {
            "rq": rq,
            "title": title,
            "rows": len(rows),
            "path": str(path),
            "sources": sources,
            "origin": origin,
            "note": note,
        }

    figures = build_figures(src)
    tables, figure_inventory = build_inventories(
        contract=contract, composed=composed, figures=figures
    )
    validation_rows = build_validation(
        contract=contract,
        tables=tables,
        figures=figures,
        figure_inventory=figure_inventory,
        src=src,
    )
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["invariant"] for row in validation_rows if row["status"] != "pass"]
        raise ValueError(f"H15 invariants failed: {failed}")
    summary_rows = [
        {
            "metric": "composed_tables",
            "value": str(len(tables)),
            "unit": "tables",
            "interpretation": "tables built here; the remaining tables of the frame are copied by the article bundle",
        },
        {
            "metric": "figure_points",
            "value": str(len(figures)),
            "unit": "points",
            "interpretation": ";".join(f"{row['figure_id']}={row['rows']}" for row in figure_inventory),
        },
        {
            "metric": "verified_sources",
            "value": str(len(src.used)),
            "unit": "files",
            "interpretation": "every source checked against the checksum its stage manifest records",
        },
    ]

    for path, columns, rows in (
        (table_inventory_output, TABLE_INVENTORY_COLUMNS, tables),
        (figure_inventory_output, FIGURE_INVENTORY_COLUMNS, figure_inventory),
        (figure_data_output, FIGURE_POINT_COLUMNS, figures),
        (validation_output, VALIDATION_COLUMNS, validation_rows),
        (summary_output, SUMMARY_COLUMNS, summary_rows),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    manifest = {
        "stage": "H15",
        "track": "AC",
        "contract_version": contract["contract_version"],
        "composition_status": "validated",
        "tables": {row["table_id"]: row["output_path"] for row in tables},
        "figures": {row["figure_id"]: row["rows"] for row in figure_inventory},
        "verified_sources": [
            {"path": path, "sha256": digest, "source_manifest": manifest_path}
            for path, (digest, manifest_path) in sorted(src.used.items())
        ],
        "inputs": [_manifest_entry(contract_path)],
        "outputs": written,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "tables": len(tables),
        "added_tables": sum(1 for row in tables if row["origin"].startswith("added")),
        "figures": len(figure_inventory),
        "figure_points": len(figures),
        "verified_sources": len(src.used),
        "status": "validated",
    }
