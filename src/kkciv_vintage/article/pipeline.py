from __future__ import annotations

import csv
import hashlib
import json
import shutil
import statistics
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


KEY_NUMBER_COLUMNS = [
    "metric_id",
    "research_question",
    "stage",
    "description",
    "value",
    "unit",
    "source_file",
    "derivation",
]
CAUSE_COLUMNS = ["cause_family", "evidence_level", "counts_toward_g1", "events", "share_of_events"]
PROPAGATION_COLUMNS = [
    "scenario_id",
    "injected_cells",
    "revised_source_mix",
    "b0_served",
    "b1_served",
    "b2_served",
    "b3_served",
    "b2_propagation_rate",
]
TREATMENTS = ["B0", "B1", "B2", "B3"]
PROCESSED = Path("results/processed")


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


def _repository_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _ratio(numerator: int | float, denominator: int | float) -> str:
    return f"{Decimal(str(numerator)) / Decimal(str(denominator)):.4f}"


def manifested_outputs(manifest_dir: Path) -> dict[str, tuple[str, str]]:
    """Map every manifested output path to its checksum and the manifest that records it."""
    index: dict[str, tuple[str, str]] = {}
    for manifest_path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("outputs", []):
            path, digest = item["path"], item["sha256"]
            if path in index and index[path][0] != digest:
                raise ValueError(f"{path} is recorded with different checksums by two manifests")
            index.setdefault(path, (digest, _repository_path(manifest_path)))
    return index


class Sources:
    """Checksum-verified access to manifested result tables."""

    def __init__(self, manifest_dir: Path) -> None:
        self.index = manifested_outputs(manifest_dir)
        self.cache: dict[str, list[dict[str, str]]] = {}
        self.used: dict[str, tuple[str, str]] = {}

    def verify(self, path: Path) -> tuple[str, str]:
        key = str(path)
        if key not in self.index:
            raise ValueError(f"{key} is not an output of any stage manifest")
        digest, manifest = self.index[key]
        if not path.exists() or _sha256(path) != digest:
            raise ValueError(f"{key} does not match the checksum recorded in {manifest}")
        self.used[key] = (digest, manifest)
        return digest, manifest

    def rows(self, name: str) -> list[dict[str, str]]:
        path = PROCESSED / name
        if name not in self.cache:
            self.verify(path)
            self.cache[name] = _read_csv(path)
        return self.cache[name]

    def metric(self, name: str, metric: str) -> str:
        values = [row["value"] for row in self.rows(name) if row["metric"] == metric]
        if len(values) != 1:
            raise ValueError(f"{name} does not contain exactly one metric {metric}")
        return values[0]


def cause_distribution(events: list[dict[str, str]]) -> list[dict[str, str]]:
    counts = Counter((row["cause_family"], row["evidence_level"], row["counts_toward_g1"]) for row in events)
    return [
        {
            "cause_family": family,
            "evidence_level": level,
            "counts_toward_g1": toward,
            "events": str(count),
            "share_of_events": _ratio(count, len(events)),
        }
        for (family, level, toward), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def revision_propagation(routes: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    scenarios = sorted({(int(row["scenario_order"]), row["scenario_id"]) for row in routes})
    for _, scenario_id in scenarios:
        by_treatment = {row["treatment_id"]: row for row in routes if row["scenario_id"] == scenario_id}
        injected = int(by_treatment["B0"]["input_rows"])
        rows.append(
            {
                "scenario_id": scenario_id,
                "injected_cells": str(injected),
                "revised_source_mix": by_treatment["B0"]["revised_source_mix"],
                **{f"{t.lower()}_served": by_treatment[t]["synthetic_observations_served"] for t in TREATMENTS},
                "b2_propagation_rate": _ratio(int(by_treatment["B2"]["synthetic_observations_served"]), injected),
            }
        )
    return rows


def key_numbers(src: Sources) -> list[dict[str, str]]:
    numbers: list[dict[str, str]] = []

    def add(metric_id: str, rq: str, stage: str, description: str, value: Any, unit: str, source: str, derivation: str) -> None:
        numbers.append(
            {
                "metric_id": metric_id,
                "research_question": rq,
                "stage": stage,
                "description": description,
                "value": str(value),
                "unit": unit,
                "source_file": str(PROCESSED / source) if not source.startswith("data/") else source,
                "derivation": derivation,
            }
        )

    def count(name: str, predicate: Callable[[dict[str, str]], bool]) -> int:
        return sum(1 for row in src.rows(name) if predicate(row))

    coverage = "h1-indicator-coverage.csv"
    add("p1_indicator_candidates", "P1", "H1", "Kandidat indikator yang dinilai", len(src.rows(coverage)), "indikator", coverage, "jumlah baris")
    for status in ("verified", "partial", "unavailable"):
        add(f"p1_indicator_{status}", "P1", "H1", f"Indikator berstatus {status}", count(coverage, lambda r, s=status: r["derived_status"] == s), "indikator", coverage, f"derived_status = {status}")

    pilot = "h2-indicator-summary.csv"
    add("p1_pilot_overlap_cells", "P1", "H2", "Sel beririsan pada pilot dua kanal", sum(int(r["overlap_cells"] or 0) for r in src.rows(pilot)), "sel", pilot, "jumlah overlap_cells")
    add("p1_pilot_value_mismatches", "P1", "H2", "Sel beririsan yang nilainya berbeda", sum(int(r["value_mismatches"] or 0) for r in src.rows(pilot)), "sel", pilot, "jumlah value_mismatches")

    add("p1_main_compared_cells", "P1", "H3", "Sel nasional-provinsi yang dibandingkan WebAPI vs TPB 2024", len(src.rows("h3-cell-comparison.csv")), "sel", "h3-cell-comparison.csv", "jumlah baris")
    add("p1_main_discrepant_cells", "P1", "H3", "Sel yang nilainya berbeda", len(src.rows("h3-discrepancies.csv")), "sel", "h3-discrepancies.csv", "jumlah baris")
    add("p1_granularity_checks", "P1", "H3", "Pemeriksaan nilai nasional terhadap provinsi", len(src.rows("h3-granularity.csv")), "pemeriksaan", "h3-granularity.csv", "jumlah baris")
    add("p1_national_within_province_range", "P1", "H3", "Nilai nasional yang berada dalam rentang provinsi", count("h3-granularity.csv", lambda r: r["national_within_province_range"].lower() in {"yes", "true"}), "pemeriksaan", "h3-granularity.csv", "national_within_province_range = yes")
    add("p1_release_cell_keys", "P1", "H3", "Kunci sel pada perbandingan antarrilis", len(src.rows("h3-release-cell-comparison.csv")), "kunci sel", "h3-release-cell-comparison.csv", "jumlah baris")
    add("p1_release_discrepancies", "P1", "H3", "Perbedaan nilai antarrilis", len(src.rows("h3-release-discrepancies.csv")), "sel", "h3-release-discrepancies.csv", "jumlah baris")
    add("p1_release_discrepancy_domains", "P1", "H3", "Domain yang mempunyai perbedaan antarrilis", len({r["domain"] for r in src.rows("h3-release-discrepancies.csv")}), "domain", "h3-release-discrepancies.csv", "jumlah domain unik")

    events = "h5-confirmed-events.csv"
    total_events = len(src.rows(events))
    core = count(events, lambda r: r["evidence_level"] == "observed" and r["cause_family"] in {"vintage", "methodology", "granularity"})
    toward = count(events, lambda r: r["counts_toward_g1"] == "yes")
    add("p1_classified_events", "P1", "H4-H5", "Kejadian ketidaksesuaian yang diklasifikasikan", total_events, "kejadian", events, "jumlah baris")
    add("p1_confirmed_core_events", "P1", "H5", "Kejadian dengan sebab inti terkonfirmasi (vintage, metodologi, granularitas)", core, "kejadian", events, "evidence_level = observed dan cause_family inti")
    add("p1_confirmed_core_share", "P1", "H5", "Proporsi sebab inti terkonfirmasi", _ratio(core, total_events), "rasio", events, "p1_confirmed_core_events / p1_classified_events")
    add("p1_core_share_incl_candidates", "P1", "H5", "Proporsi sebab inti bila kandidat ikut dihitung", _ratio(toward, total_events), "rasio", events, "counts_toward_g1 = yes / jumlah kejadian")
    for family in ("granularity", "vintage", "methodology", "rounding_or_presentation"):
        add(f"p1_{family}_observed", "P1", "H5", f"Kejadian {family} terkonfirmasi", count(events, lambda r, f=family: r["cause_family"] == f and r["evidence_level"] == "observed"), "kejadian", events, f"cause_family = {family}, evidence_level = observed")
    g1_share = next(r["value"] for r in src.rows("h5-gate-g1-summary.csv") if r["criterion"].startswith("G1.2"))
    if g1_share != _ratio(core, total_events):
        raise ValueError("confirmed core share disagrees with the H5 Gate G1 summary")
    traces = "h5-revision-traces.csv"
    add("p1_revision_traces", "P1", "H5", "Jejak revisi antarrilis yang dibekukan", len({r["trace_id"] for r in src.rows(traces)}), "jejak", traces, "jumlah trace_id unik")
    add("p1_trace_vintage_rows", "P1", "H5", "Baris vintage pada jejak revisi", len(src.rows(traces)), "baris", traces, "jumlah baris")

    add("p2_vintages", "P2", "H6", "Vintage (rilis) pada workload nyata", len(src.rows("h6-release-vintages.csv")), "vintage", "h6-release-vintages.csv", "jumlah baris")
    add("p2_observations", "P2", "H6", "Observasi sel indikator dengan vintage eksplisit", len(src.rows("h6-indicator-observations.csv")), "observasi", "h6-indicator-observations.csv", "jumlah baris")
    add("p2_stable_cells", "P2", "H6", "Sel indikator stabil lintas rilis", len({r["cell_id"] for r in src.rows("h6-indicator-observations.csv")}), "sel", "h6-indicator-observations.csv", "jumlah cell_id unik")
    add("p2_b3_asof_rows", "P2", "H9A", "Baris state per rilis yang direkonstruksi B3 dari kunci vintage", len(src.rows("h9-b3-asof-states.csv")), "baris", "h9-b3-asof-states.csv", "jumlah baris; sama dengan snapshot B1")

    b3 = "h9-b3-summary.csv"
    add("p3_b3_recomputed_cells", "P3", "H9A", "Evaluasi sel inkremental B3 pada tiga rilis nyata", src.metric(b3, "recomputed_cells"), "evaluasi sel", b3, "metric recomputed_cells")
    add("p3_full_recompute_cells", "P3", "H9A", "Evaluasi sel bila dihitung ulang penuh setiap rilis", src.metric(b3, "full_recompute_cells"), "evaluasi sel", b3, "metric full_recompute_cells")
    add("p3_recompute_ratio", "P3", "H9A", "Rasio kerja logis inkremental / penuh", src.metric(b3, "recompute_ratio"), "rasio", b3, "metric recompute_ratio")
    add("p3_b3_logical_rows", "P3", "H9A", "Baris logis B3 (store + serving)", src.metric(b3, "logical_materialized_rows"), "baris", b3, "metric logical_materialized_rows")
    add("p3_b1_logical_rows", "P3", "H8A", "Kemunculan baris logis B1 (3 snapshot penuh)", src.metric("h8-b1-summary.csv", "logical_full_copy_rows"), "baris", "h8-b1-summary.csv", "metric logical_full_copy_rows")

    routes = "h9b-route-executions.csv"
    def route_sum(treatment: str, column: str) -> int:
        return sum(int(r[column]) for r in src.rows(routes) if r["treatment_id"] == treatment)
    add("p3_injected_rows", "P3", "H9B", "Revisi tersuntik pada lima skenario validasi", route_sum("B0", "input_rows"), "revisi", routes, "jumlah input_rows B0")
    add("p3_b3_injected_recomputed", "P3", "H9B", "Sel yang dihitung ulang B3 pada revisi tersuntik", route_sum("B3", "cells_evaluated"), "evaluasi sel", routes, "jumlah cells_evaluated B3")
    add("p3_b1_injected_rows_written", "P3", "H9B", "Baris logis yang ditulis B1 pada revisi tersuntik", route_sum("B1", "rows_written_logical"), "baris", routes, "jumlah rows_written_logical B1")
    add("p3_b3_injected_rows_written", "P3", "H9B", "Baris logis yang ditulis B3 pada revisi tersuntik", route_sum("B3", "rows_written_logical"), "baris", routes, "jumlah rows_written_logical B3")

    storage = {r["treatment_id"]: r for r in src.rows("h10-storage-by-treatment.csv")}
    for treatment in TREATMENTS:
        row = storage[treatment]
        add(f"p3_{treatment.lower()}_bytes_median", "P3", "H10A", f"Ruang fisik {treatment} (median 3 repetisi)", row["total_bytes_median"], "byte", "h10-storage-by-treatment.csv", f"total_bytes_median; rentang {row['total_bytes_min']}-{row['total_bytes_max']}")
        add(f"p3_{treatment.lower()}_data_bytes_median", "P3", "H10A", f"Ruang data Parquet {treatment}", row["data_bytes_median"], "byte", "h10-storage-by-treatment.csv", "data_bytes_median")
        add(f"p3_{treatment.lower()}_metadata_bytes_median", "P3", "H10A", f"Ruang metadata Iceberg {treatment}", row["metadata_bytes_median"], "byte", "h10-storage-by-treatment.csv", "metadata_bytes_median")
    tables = src.rows("h10-storage-tables.csv")
    def table_median(suffix: str) -> int:
        return int(statistics.median(int(r["reachable_bytes"]) for r in tables if r["table"].endswith(suffix)))
    store, serving = table_median("b3_observation_vintages"), table_median("b3_indicator_current")
    add("p3_b3_store_bytes_median", "P3", "H10A", "Ruang fisik store B3 saja", store, "byte", "h10-storage-tables.csv", "median reachable_bytes b3_observation_vintages")
    add("p3_b3_serving_bytes_median", "P3", "H10A", "Ruang fisik tabel serving B3", serving, "byte", "h10-storage-tables.csv", "median reachable_bytes b3_indicator_current")
    b1_bytes = int(storage["B1"]["total_bytes_median"])
    add("p3_b3_over_b1_bytes", "P3", "H10A", "Rasio ruang B3 total / B1", _ratio(int(storage["B3"]["total_bytes_median"]), b1_bytes), "rasio", "h10-storage-by-treatment.csv", "p3_b3_bytes_median / p3_b1_bytes_median")
    add("p3_b3_store_over_b1_bytes", "P3", "H10A", "Rasio ruang store B3 / B1", _ratio(store, b1_bytes), "rasio", "h10-storage-tables.csv", "p3_b3_store_bytes_median / p3_b1_bytes_median")

    cost = {(r["scenario_id"], r["treatment_id"]): r for r in src.rows("h10b-apply-cost.csv")}
    smoke = "validation_001"
    for treatment in TREATMENTS:
        row = cost[(smoke, treatment)]
        add(f"p3_{treatment.lower()}_revision_write_seconds", "P3", "H10B", f"Waktu tulis satu revisi 1 sel, {treatment}", row["write_seconds_median"], "detik", "h10b-apply-cost.csv", f"write_seconds_median {smoke}; rentang {row['write_seconds_min']}-{row['write_seconds_max']}; {row['write_statements']} pernyataan")
        add(f"p3_{treatment.lower()}_revision_total_seconds", "P3", "H10B", f"Waktu tulis dan pemeliharaan satu revisi 1 sel, {treatment}", row["total_seconds_median"], "detik", "h10b-apply-cost.csv", f"total_seconds_median {smoke}; pemeliharaan {row['maintenance_seconds_median']}")
        add(f"p3_{treatment.lower()}_revision_delta_bytes", "P3", "H10B", f"Pertambahan byte satu revisi 1 sel, {treatment}", row["delta_bytes_median"], "byte", "h10b-apply-cost.csv", f"delta_bytes_median {smoke}; data {row['delta_data_bytes_median']}; metadata {row['delta_metadata_bytes_median']}")

    repro = {r["treatment_id"]: r for r in src.rows("h9c-reproducibility-table.csv")}
    recall = src.rows("h10-recall-after-restart.csv")
    for treatment in TREATMENTS:
        add(f"p4_{treatment.lower()}_success_rate", "P4", "H9C", f"Tingkat keberhasilan memanggil 38 angka terbit, {treatment}", repro[treatment]["success_rate"], "rasio", "h9c-reproducibility-table.csv", "success_rate")
        recalled = sum(1 for r in recall if r["treatment_id"] == treatment and r["addressable"] == "yes")
        if _ratio(recalled, 38) != repro[treatment]["success_rate"]:
            raise ValueError(f"physical recall of {treatment} disagrees with the H9C audit")
        add(f"p4_{treatment.lower()}_recalled_after_restart", "P4", "H10A", f"Angka terbit yang dipanggil ulang fisik setelah restart katalog, {treatment}", recalled, "permintaan dari 38", "h10-recall-after-restart.csv", "addressable = yes")
    after_revision = src.rows("h10b-recall-after-revision.csv")
    for treatment in TREATMENTS:
        served = sum(
            1
            for r in after_revision
            if r["treatment_id"] == treatment and r["scenario_id"] == smoke and r["addressable"] == "yes"
        )
        add(f"p4_{treatment.lower()}_recalled_after_revision", "P4", "H10B", f"Permintaan yang dipanggil ulang fisik setelah satu revisi tersuntik, {treatment}", served, "permintaan dari 39", "h10b-recall-after-revision.csv", f"addressable = yes pada {smoke}")

    add("p4_lineage_paths", "P4", "H9C", "Path lineage sumber-sampai-tabel empat perlakuan", src.metric("h9c-summary.csv", "closed_lineage_paths"), "path", "h9c-summary.csv", "metric closed_lineage_paths")
    add("p4_lineage_completeness", "P4", "H9C", "Kelengkapan lineage", src.metric("h9c-summary.csv", "closure_completeness"), "rasio", "h9c-summary.csv", "metric closure_completeness")

    for row in src.rows("h6b-source-trust-scores.csv"):
        add(f"b2_trust_score_{row['source_id']}", "B2", "H6B", f"Skor kepercayaan beku {row['source_id']}", row["trust_score"], "skor", "h6b-source-trust-scores.csv", "trust_score")
    add("b2_selected_non_latest", "B2", "H7B", "Sel B2 yang menyajikan nilai bukan vintage terbaru (data nyata)", src.metric("h7b-b2-summary.csv", "older_vintage_selected"), "sel dari 14", "h7b-b2-summary.csv", "metric older_vintage_selected")
    injected = route_sum("B0", "input_rows")
    for treatment in TREATMENTS:
        served = route_sum(treatment, "synthetic_observations_served")
        add(f"b2_propagation_{treatment.lower()}", "B2", "H9B", f"Tingkat propagasi revisi tersuntik, {treatment}", _ratio(served, injected), "rasio", routes, f"{served}/{injected} synthetic_observations_served / input_rows")
    return numbers


def run_bundle(
    *,
    tables_config: Path,
    manifest_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    src = Sources(manifest_dir)
    config = _read_csv(tables_config)
    if len({row["source_path"] for row in config}) != len(config):
        raise ValueError("article bundle config lists a source twice")

    expected: set[Path] = set()
    copied: list[dict[str, Any]] = []
    for row in config:
        source = Path(row["source_path"])
        digest, manifest = src.verify(source)
        target = output_dir / row["group"] / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if _sha256(target) != digest:
            raise ValueError(f"copy of {source} does not match its source checksum")
        expected.add(target)
        copied.append(
            {
                "path": str(target.relative_to(output_dir)),
                "group": row["group"],
                "description": row["description"],
                "rows": len(_read_csv(target)),
                "sha256": digest,
                "source_path": str(source),
                "source_manifest": manifest,
            }
        )

    derived: list[dict[str, Any]] = []
    for path, columns, rows, description in (
        (output_dir / "p1-karakterisasi" / "p1-distribusi-sebab.csv", CAUSE_COLUMNS, cause_distribution(src.rows("h5-confirmed-events.csv")), "Distribusi 123 kejadian menurut sebab dan tingkat bukti setelah H5"),
        (output_dir / "p3-ongkos" / "p3-propagasi-revisi.csv", PROPAGATION_COLUMNS, revision_propagation(src.rows("h9b-route-executions.csv")), "Revisi tersuntik yang tampil di state serving per skenario dan perlakuan"),
        (output_dir / "angka-kunci.csv", KEY_NUMBER_COLUMNS, key_numbers(src), "Angka kunci naskah beserta sumber dan cara penurunannya"),
    ):
        digest = _write_csv(path, columns, rows)
        expected.add(path)
        derived.append({"path": str(path.relative_to(output_dir)), "description": description, "rows": len(rows), "sha256": digest})

    stale = [path for path in output_dir.rglob("*.csv") if path not in expected]
    for path in stale:
        path.unlink()

    manifest = {
        "bundle": "vintage_reconciliation_article_data",
        "bundle_status": "verified",
        "copied_tables": copied,
        "derived_tables": derived,
        "verified_sources": [
            {"path": path, "sha256": digest, "source_manifest": manifest_path}
            for path, (digest, manifest_path) in sorted(src.used.items())
        ],
        "inputs": [{"path": _repository_path(tables_config), "sha256": _sha256(tables_config)}],
    }
    (output_dir / "bundle-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "copied_tables": len(copied),
        "derived_tables": len(derived),
        "key_numbers": derived[-1]["rows"],
        "verified_sources": len(src.used),
        "removed_stale": len(stale),
        "status": "verified",
    }
