from __future__ import annotations

import csv
import hashlib
import json
import statistics
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h6.pipeline import (
    OBSERVATION_COLUMNS,
    VINTAGE_COLUMNS,
    WEBAPI_VAR,
    _decimal_parts,
    _id,
)
from kkciv_vintage.h6c.pipeline import build_lineage
from kkciv_vintage.h7.pipeline import STATE_COLUMNS as B0_STATE_COLUMNS
from kkciv_vintage.h7.pipeline import simulate_overwrite
from kkciv_vintage.h8.pipeline import CATALOG_COLUMNS as B1_CATALOG_COLUMNS
from kkciv_vintage.h8.pipeline import SNAPSHOT_STATE_COLUMNS as B1_STATE_COLUMNS
from kkciv_vintage.h8b.pipeline import (
    INJECTION_COLUMNS,
    PLAN_COLUMNS,
    PROTECTED_DIMENSIONS,
    _format_lexeme,
    _format_storage,
    _payload_hash,
    _short_hash,
)
from kkciv_vintage.h9.pipeline import CURRENT_COLUMNS as B3_CURRENT_COLUMNS
from kkciv_vintage.h9.pipeline import IMPACT_RELATIONSHIP, lineage_impact_index
from kkciv_vintage.h9.pipeline import STORE_COLUMNS as B3_STORE_COLUMNS
from kkciv_vintage.h9.pipeline import simulate_vintage_aware
from kkciv_vintage.h9b.pipeline import (
    SYNTHETIC_EVIDENCE,
    SYNTHETIC_SOURCE,
    select_single_source,
    synthetic_lineage,
    synthetic_observations,
    synthetic_vintage_row,
)
from kkciv_vintage.h10b.pipeline import B2_SELECTION_COLUMNS, b2_selection_state


TREATMENTS = ["B0", "B1", "B2", "B3"]
CLASSES = ["data", "delete", "manifest", "manifest_list", "metadata_json"]
SIZED_CLASSES = {"data", "delete", "manifest"}
PHASES = ["baseline", "after_revision"]
REQUEST_KINDS = ["official", "synthetic"]
REQUIRED_DECISIONS = {
    "h10c_sweep_workload": ("experiment_freeze", "hybrid_fixture_plus_province_panel"),
    "h10c_sweep_universe": ("injection_size", "productivity_growth_2025_province_webapi"),
    "h10c_panel_deduplication": ("workload", "drop_duplicate_cell_source_rows_verified_identical"),
    "h10c_propagation_metric": ("metrics", "freeze_revision_propagation_as_supporting_metric"),
    "h10c_resource_limit": ("resource_limit", "freeze_2vcpu_vm_as_the_experiment_resource_limit"),
}
# The synthetic revision is the fifth arrival; the four panel vintages come first.
PANEL_ARRIVALS = 4
SYNTHETIC_ARRIVAL_ORDER = str(PANEL_ARRIVALS + 1)
SYNTHETIC_SNAPSHOT_ORDER = str(PANEL_ARRIVALS + 1)
PANEL_EVIDENCE_LEVEL = "official_panel"
TRANSFORMATION_VERSION = "h11-sweep-v1"

DUPLICATE_COLUMNS = [
    "cell_id",
    "source_id",
    "kept_input_dataset",
    "kept_source_record_id",
    "kept_retrieved_at",
    "dropped_input_dataset",
    "dropped_source_record_id",
    "dropped_retrieved_at",
    "value_lexeme",
    "unit",
    "values_identical",
]
IMPACT_EDGE_COLUMNS = [
    "edge_id",
    "observation_id",
    "cell_id",
    "vintage_id",
    "source_id",
    "arrival_order",
    "relationship",
]
B3_STORE_OUTPUT_COLUMNS = B3_STORE_COLUMNS
SYNTHETIC_STORE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    *OBSERVATION_COLUMNS,
    "source_id",
    "vintage_date",
    "vintage_retrieved_at",
    "arrival_order",
    "revised_source_id",
    "base_observation_id",
    "base_vintage_id",
    "snapshot_order",
]
PANEL_VINTAGE_COLUMNS = [*VINTAGE_COLUMNS, "arrival_order"]
SYNTHETIC_VINTAGE_COLUMNS = [
    "scenario_order",
    "scenario_id",
    *PANEL_VINTAGE_COLUMNS,
    "snapshot_order",
    "state_snapshot_key",
]
DIRTY_CELL_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "cell_id",
    "base_observation_id",
    "synthetic_observation_id",
    "lineage_edge_id",
    "impact_basis",
]
SCENARIO_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "cells_revised",
    "selection_share",
    "seed",
    "revised_source_id",
    "synthetic_vintage_id",
    "synthetic_vintage_date",
    "workload_sha256",
    "nested_from_previous",
    "panel_observations",
    "panel_cells",
    "requests",
    *[f"{treatment.lower()}_expected_rows" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_expected_cells" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_cells_evaluated" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_rows_written_logical" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_cells_changed" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_propagated_revisions" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_expected_recalled" for treatment in TREATMENTS],
    *[f"{treatment.lower()}_expected_snapshots" for treatment in TREATMENTS],
]
EXPECTED_REVISED_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "treatment_id",
    "selection_rank",
    "cell_id",
    "revised_observation_id",
    "revised_value_lexeme",
    "served_observation_id",
    "served_value_lexeme",
    "revision_served",
    "base_value_recallable",
]
EXPECTED_RECALL_COLUMNS = [
    "scenario_order",
    "scenario_id",
    "treatment_id",
    "request_kind",
    "requests",
    "expected_addressable",
    "expected_unavailable",
]
BASELINE_COLUMNS = [
    "treatment_id",
    "table",
    "expected_rows",
    "expected_cells",
    "expected_snapshots",
    "load_statements",
    "detail",
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


def validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("contract_version") != "h11.1"
        or contract.get("stage") != "H11"
        or contract.get("track") != "B"
    ):
        raise ValueError("unsupported H11 contract")
    if contract["human_decisions"]["decision_ids"] != list(REQUIRED_DECISIONS):
        raise ValueError("H11 human decisions do not match the approved H10C registry")
    panel = contract["panel"]
    if panel["observations"] != 6983 or panel["cells"] != 5378 or panel["input_rows"] != 7666:
        raise ValueError("H11 panel shape does not match the frozen F2.3 panel")
    if panel["deduplication"]["key"] != ["cell_id", "source_id"] or panel["deduplication"]["dropped_rows"] != 683:
        raise ValueError("H11 must drop the 683 frozen duplicate rows on the frozen key")
    if panel["classification_columns"]["evidence_level"] != PANEL_EVIDENCE_LEVEL:
        raise ValueError("H11 panel evidence level does not match the implementation")
    if list(contract["tables"]) != TREATMENTS:
        raise ValueError("H11 must measure B0 B1 B2 and B3")
    if contract["universe"]["cells"] != 38 or contract["universe"]["seed"] != "20260912":
        raise ValueError("H11 universe does not match the frozen F6.4 universe")
    scenarios = contract["scenarios"]
    sizes = [int(row["cells"]) for row in sorted(scenarios, key=lambda row: int(row["scenario_order"]))]
    if sizes != [1, 2, 4, 8, 16, 38]:
        raise ValueError("H11 scenario sizes do not match the frozen F6.3 sweep")
    protocol = contract["protocol"]
    if protocol["repetitions"] < 3:
        raise ValueError("H11 requires at least three repetitions per point")
    if set(protocol["injection"]) != set(TREATMENTS) or set(protocol["baseline_mechanisms"]) != set(TREATMENTS):
        raise ValueError("H11 needs a baseline and an injection mechanism per treatment")
    footprint = contract["footprint"]
    if footprint["classes"] != CLASSES or footprint["phases"] != PHASES:
        raise ValueError("H11 footprint classes or phases do not match the implementation")
    timing = contract["timing"]
    if (
        timing["environment_decision"] != "h10b_timing_environment"
        or timing["resource_decision"] != "h10c_resource_limit"
        or not timing["claim_limit"]
    ):
        raise ValueError("H11 timing must cite both frozen environment decisions and its claim limit")
    if contract["measurement_boundary"]["sweep_status"] != "main_sweep":
        raise ValueError("H11 is the main sweep and must say so")
    if contract["breakeven"]["interpolation"] != "never":
        raise ValueError("H11 must report only swept sizes")


def validate_human_decisions(rows: list[dict[str, str]]) -> None:
    by_id = {row["decision_id"]: row for row in rows}
    if len(by_id) != len(rows) or not set(REQUIRED_DECISIONS) <= set(by_id):
        raise ValueError("H11 requires the five approved H10C sweep decisions")
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
            raise ValueError(f"H11 human decision {decision_id} is not approved as recorded")


def verify_freeze(freeze_rows: list[dict[str, str]], required_ids: list[str]) -> list[dict[str, str]]:
    """Re-check every frozen evidence file against the checksum recorded at the freeze."""
    by_id = {row["freeze_id"]: row for row in freeze_rows}
    if missing := [freeze_id for freeze_id in required_ids if freeze_id not in by_id]:
        raise ValueError(f"H11 is missing frozen items {missing}")
    checked: list[dict[str, str]] = []
    for row in freeze_rows:
        path = Path(row["evidence_path"])
        if not path.exists():
            raise ValueError(f"frozen evidence {path} is gone")
        actual = _sha256(path)
        if actual != row["evidence_sha256"]:
            raise ValueError(f"frozen evidence {path} changed after the freeze")
        checked.append({**row, "verified_sha256": actual})
    return checked


def deduplicate_panel(
    rows: list[dict[str, str]],
    *,
    retrieved_at_for: Any,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Keep one row per (cell_id, source_id) and prove every dropped row identical.

    The frozen reason is B3: its store is keyed by (cell_id, vintage_id), and two
    WebAPI variables carry the same indicator for the same cell.
    """
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        cell_id = _id(
            row["indicator_key"],
            row["series_key"],
            row["observed_period"],
            row["geo_level"],
            row["geo_code"],
        )
        annotated = {
            **row,
            "cell_id": cell_id,
            "retrieved_at": retrieved_at_for(row),
        }
        groups.setdefault((cell_id, row["source_id"]), []).append(annotated)

    kept: list[dict[str, str]] = []
    duplicates: list[dict[str, str]] = []
    for (cell_id, source_id), candidates in sorted(groups.items()):
        ordered = sorted(
            candidates, key=lambda row: (_negated(row["retrieved_at"]), row["source_record_id"])
        )
        winner = ordered[0]
        kept.append(winner)
        for loser in ordered[1:]:
            identical = (
                Decimal(loser["value"]) == Decimal(winner["value"])
                and loser["value"] == winner["value"]
                and loser["unit"] == winner["unit"]
            )
            if not identical:
                raise ValueError(
                    f"H11 refuses to drop a duplicate that differs in value: {cell_id} {source_id}"
                )
            duplicates.append(
                {
                    "cell_id": cell_id,
                    "source_id": source_id,
                    "kept_input_dataset": winner["input_dataset"],
                    "kept_source_record_id": winner["source_record_id"],
                    "kept_retrieved_at": winner["retrieved_at"],
                    "dropped_input_dataset": loser["input_dataset"],
                    "dropped_source_record_id": loser["source_record_id"],
                    "dropped_retrieved_at": loser["retrieved_at"],
                    "value_lexeme": winner["value"],
                    "unit": winner["unit"],
                    "values_identical": "yes",
                }
            )
    return kept, duplicates


def _negated(text: str) -> tuple[int, ...]:
    """Sort key that orders strings descending inside an ascending sort."""
    return tuple(-ord(character) for character in text)


def project_panel(
    kept_rows: list[dict[str, str]],
    *,
    publication_catalog: dict[str, Any],
    publication_manifest_path: Path,
    webapi_catalogs: dict[str, tuple[Path, dict[str, Any]]],
    webapi_variable_pattern: Any,
    batch_id: str,
    run_id: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Project the deduplicated panel into the frozen H6 vintage and observation shape."""
    pub_files = {item["source_id"]: item for item in publication_catalog["files"]}
    pub_manifest_sha = _sha256(publication_manifest_path)
    webapi_resolved: dict[str, tuple[Path, str, dict[str, Any], dict[str, Any]]] = {}
    for dataset, (path, catalog) in webapi_catalogs.items():
        webapi_resolved[dataset] = (
            path,
            _sha256(path),
            {str(item["variable_id"]): item for item in catalog["files"]},
            catalog,
        )

    vintages: dict[str, dict[str, str]] = {}
    observations: list[dict[str, str]] = []
    for row in kept_rows:
        source_id = row["source_id"]
        if source_id in pub_files:
            artifact = pub_files[source_id]
            manifest_path = publication_manifest_path
            manifest_sha = pub_manifest_sha
            retrieved_at = publication_catalog["retrieved_at"]
            source_channel = "publication_pdf"
            vintage_basis = "published_release"
            release_label = artifact["title"]
        elif source_id == "bps_webapi":
            dataset = row["input_dataset"]
            if dataset not in webapi_resolved:
                raise ValueError(f"H11 has no WebAPI manifest for dataset {dataset}")
            manifest_path, manifest_sha, api_files, catalog = webapi_resolved[dataset]
            match = webapi_variable_pattern.search(row["source_record_id"])
            if not match or match.group(1) not in api_files:
                raise ValueError(
                    f"cannot resolve WebAPI artifact for {row['source_record_id']} in {manifest_path}"
                )
            artifact = api_files[match.group(1)]
            retrieved_at = catalog["retrieved_at"]
            source_channel = "webapi"
            vintage_basis = "retrieval_snapshot"
            release_label = f"WebAPI {retrieved_at}"
        else:
            raise ValueError(f"unknown H11 panel source {source_id!r}")

        vintage_id = _id(source_id, row["release_date"], manifest_sha)
        vintage = {
            "vintage_id": vintage_id,
            "source_id": source_id,
            "source_channel": source_channel,
            "vintage_date": row["release_date"],
            "vintage_basis": vintage_basis,
            "retrieved_at": retrieved_at,
            "release_label": release_label,
            "source_manifest_path": str(manifest_path),
            "source_manifest_sha256": manifest_sha,
        }
        if vintage_id in vintages and vintages[vintage_id] != vintage:
            raise ValueError(f"conflicting H11 vintage dimension row {vintage_id}")
        vintages[vintage_id] = vintage

        value_decimal, decimal_places = _decimal_parts(row["value"])
        observations.append(
            {
                "observation_id": _id(row["cell_id"], vintage_id, row["source_record_id"]),
                "cell_id": row["cell_id"],
                "vintage_id": vintage_id,
                "domain": row["domain"],
                "indicator_key": row["indicator_key"],
                "series_key": row["series_key"],
                "observed_period": row["observed_period"],
                "period_granularity": "year",
                "geo_level": row["geo_level"],
                "geo_code": row["geo_code"],
                "geo_name": row["geo_name"],
                "unit": row["unit"],
                "value_decimal": value_decimal,
                "value_lexeme": row["value"],
                "published_decimal_places": decimal_places,
                "producer": row["producer"],
                "methodology_version": row["methodology_version"],
                "source_artifact_path": artifact["raw_path"],
                "source_artifact_sha256": artifact["sha256"],
                "source_record_id": row["source_record_id"],
                "ingestion_batch_id": batch_id,
                "transformation_run_id": run_id,
                "transformation_version": TRANSFORMATION_VERSION,
                "trace_id": "",
                "cause_family": "",
                "evidence_level": PANEL_EVIDENCE_LEVEL,
            }
        )

    if len({row["observation_id"] for row in observations}) != len(observations):
        raise ValueError("H11 panel observation IDs are not unique")
    keys = [(row["cell_id"], row["vintage_id"]) for row in observations]
    if len(set(keys)) != len(keys):
        raise ValueError("H11 panel violates the (cell_id, vintage_id) key B3 requires")
    return (
        sorted(vintages.values(), key=lambda row: (row["vintage_date"], row["retrieved_at"], row["vintage_id"])),
        sorted(observations, key=lambda row: (row["cell_id"], row["vintage_id"])),
    )


def arrival_order(vintages: list[dict[str, str]]) -> dict[str, int]:
    """The frozen arrival order of the releases: vintage date, then retrieval, then id."""
    ordered = sorted(
        vintages, key=lambda row: (row["vintage_date"], row["retrieved_at"], row["vintage_id"])
    )
    return {row["vintage_id"]: order for order, row in enumerate(ordered, start=1)}


def full_snapshot_states(
    vintages: list[dict[str, str]], observations: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Build one complete B1 state per release.

    This repeats the H8 B1 semantics, but without the H8 invariant that every
    release covers the same cells: the panel grows as releases arrive, so an early
    state is a complete state of the cells published at that point, not of all cells.
    """
    orders = arrival_order(vintages)
    by_vintage: dict[str, list[dict[str, str]]] = {}
    for row in observations:
        by_vintage.setdefault(row["vintage_id"], []).append(row)
    state: dict[str, dict[str, str]] = {}
    states: list[dict[str, str]] = []
    catalog: list[dict[str, str]] = []
    for vintage in sorted(vintages, key=lambda row: orders[row["vintage_id"]]):
        order = orders[vintage["vintage_id"]]
        incoming = sorted(
            by_vintage.get(vintage["vintage_id"], []),
            key=lambda row: (row["cell_id"], row["observation_id"]),
        )
        if not incoming:
            raise ValueError(f"panel vintage {vintage['vintage_id']} has no observations")
        if len({row["cell_id"] for row in incoming}) != len(incoming):
            raise ValueError(f"panel vintage {vintage['vintage_id']} contains duplicate cells")
        inserted = overwritten = changed = same = 0
        for row in incoming:
            previous = state.get(row["cell_id"])
            if previous is None:
                inserted += 1
            else:
                overwritten += 1
                if Decimal(previous["value_decimal"]) == Decimal(row["value_decimal"]):
                    same += 1
                else:
                    changed += 1
            state[row["cell_id"]] = row
        snapshot_key = _id("H11", "b1_state", vintage["vintage_id"], str(order))
        for row in sorted(state.values(), key=lambda item: item["cell_id"]):
            states.append(
                {
                    **row,
                    "snapshot_order": str(order),
                    "state_snapshot_key": snapshot_key,
                    "applied_vintage_id": vintage["vintage_id"],
                }
            )
        catalog.append(
            {
                "snapshot_order": str(order),
                "state_snapshot_key": snapshot_key,
                "applied_vintage_id": vintage["vintage_id"],
                "source_id": vintage["source_id"],
                "vintage_date": vintage["vintage_date"],
                "input_rows": str(len(incoming)),
                "inserted_rows": str(inserted),
                "overwritten_rows": str(overwritten),
                "value_changed_rows": str(changed),
                "same_value_overwrites": str(same),
                "state_rows": str(len(state)),
                "state_sha256": hashlib.sha256(
                    "\n".join(
                        f"{row['cell_id']}\x1f{row['observation_id']}\x1f{row['value_decimal']}"
                        for row in sorted(state.values(), key=lambda item: item["cell_id"])
                    ).encode("utf-8")
                ).hexdigest(),
            }
        )
    return catalog, states


def execute_panel_treatments(
    *,
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    scores: list[dict[str, str]],
    scoring_source_by_observation: dict[str, str],
    selection_contract_version: str,
    selection_run_id: str,
) -> dict[str, Any]:
    """Run the four frozen treatments over one panel state, revised or not.

    Every treatment keeps the mechanism frozen at H7-H9: B0 overwrites, B1 stores one
    complete state per release, B2 selects one source with the frozen H6B score, and B3
    appends every vintage and recomputes only the cells the lineage marks dirty.
    """
    score_by_source = {row["source_id"]: Decimal(row["trust_score"]) for row in scores}
    _, b0_state, _, b0_metrics = simulate_overwrite(vintages, observations)
    b1_catalog, b1_states = full_snapshot_states(vintages, observations)
    b2_selected = select_single_source(
        vintages, observations, score_by_source, scoring_source_by_observation
    )
    b2_state = b2_selection_state(
        selected=b2_selected,
        observations=observations,
        vintages=vintages,
        scores=scores,
        scoring_source_by_observation=scoring_source_by_observation,
        selection_contract_version=selection_contract_version,
        selection_run_id=selection_run_id,
    )
    b3_arrivals, b3_store, b3_impact, b3_current, b3_asof, b3_reads, b3_metrics = (
        simulate_vintage_aware(vintages, observations, nodes, edges)
    )
    b1_current = [row for row in b1_states if row["snapshot_order"] == str(len(b1_catalog))]
    cells = {row["cell_id"] for row in observations}
    for treatment, served in (("B0", b0_state), ("B1", b1_current), ("B2", b2_state), ("B3", b3_current)):
        if {row["cell_id"] for row in served} != cells or len(served) != len(cells):
            raise ValueError(f"{treatment} does not serve exactly one row per panel cell")

    b0_addressable = {row["observation_id"] for row in b0_state}
    b1_addressable = {row["observation_id"] for row in b1_states}
    b2_addressable = {row["observation_id"] for row in b2_state}
    b3_addressable = {row["observation_id"] for row in b3_store}
    if b3_addressable != {row["observation_id"] for row in observations}:
        raise ValueError("B3 store does not hold every observation of the panel")
    return {
        "B0": {"serving": b0_state, "addressable": b0_addressable, "metrics": b0_metrics},
        "B1": {
            "serving": b1_current,
            "states": b1_states,
            "catalog": b1_catalog,
            "addressable": b1_addressable,
        },
        "B2": {"serving": b2_state, "addressable": b2_addressable},
        "B3": {
            "serving": b3_current,
            "store": b3_store,
            "impact": b3_impact,
            "arrivals": b3_arrivals,
            "asof": b3_asof,
            "reads": b3_reads,
            "addressable": b3_addressable,
            "metrics": b3_metrics,
        },
    }


def rank_universe(cell_ids: list[str], seed: str) -> list[str]:
    """The frozen F6.4 ranking: sha256(seed, cell_id), then cell_id."""
    return sorted(
        cell_ids,
        key=lambda cell_id: (
            hashlib.sha256(f"{seed}\x1f{cell_id}".encode("utf-8")).hexdigest(),
            cell_id,
        ),
    )


def build_sweep_payload(
    *,
    scenarios: list[dict[str, str]],
    universe: list[dict[str, str]],
    base_by_cell: dict[str, dict[str, str]],
    source_by_vintage: dict[str, str],
    contract_universe: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Rebuild the frozen sweep payload and check it against the frozen universe file."""
    ordered = sorted(scenarios, key=lambda row: int(row["scenario_order"]))
    seeds = {row["seed"] for row in ordered}
    if len(seeds) != 1 or next(iter(seeds)) != contract_universe["seed"]:
        raise ValueError("H11 scenarios must share the frozen sweep seed")
    seed = next(iter(seeds))
    if [row["profile_status"] for row in ordered] != ["main_sweep"] * len(ordered):
        raise ValueError("H11 scenarios must be labeled main_sweep")
    if {row["revised_source_id"] for row in ordered} != {contract_universe["base_source_id"]}:
        raise ValueError("H11 scenarios must revise exactly the frozen source")

    frozen_ranks = sorted(universe, key=lambda row: int(row["selection_rank"]))
    if [int(row["selection_rank"]) for row in frozen_ranks] != list(range(1, len(universe) + 1)):
        raise ValueError("the frozen universe ranking is not contiguous from one")
    ranked = rank_universe([row["cell_id"] for row in universe], seed)
    if ranked != [row["cell_id"] for row in frozen_ranks]:
        raise ValueError("H11 cannot reproduce the frozen universe ranking from the seed")

    for row in frozen_ranks:
        base = base_by_cell.get(row["cell_id"])
        if base is None:
            raise ValueError(f"universe cell {row['cell_id']} is not in the panel latest-vintage state")
        if base["value_lexeme"] != row["base_value_lexeme"]:
            raise ValueError(f"universe cell {row['cell_id']} no longer carries its frozen base value")
        if source_by_vintage[base["vintage_id"]] != row["base_source_id"]:
            raise ValueError(f"universe cell {row['cell_id']} is not served by its frozen base source")
        for column in ("indicator_key", "series_key", "observed_period", "geo_level", "geo_code", "unit"):
            if base[column] != row[column]:
                raise ValueError(f"universe cell {row['cell_id']} changed its {column}")

    plans: list[dict[str, str]] = []
    injections: list[dict[str, str]] = []
    previous_cells: set[str] = set()
    for scenario in ordered:
        count = int(scenario["selection_count"])
        selected = [base_by_cell[cell_id] for cell_id in ranked[:count]]
        synthetic_vintage_id = _short_hash(f"H11|vintage|{scenario['scenario_id']}|{seed}|{count}")
        scenario_rows: list[dict[str, str]] = []
        for rank, base in enumerate(selected, start=1):
            places = int(base["published_decimal_places"])
            if places < 0 or places > 10:
                raise ValueError("H11 published_decimal_places must be between zero and ten")
            before = Decimal(base["value_decimal"])
            step = Decimal(1).scaleb(-places)
            delta = -step if base["unit"].casefold() == "percent" and before + step > 100 else step
            after = before + delta
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
                "synthetic_observation_id": _short_hash(
                    f"H11|observation|{scenario['scenario_id']}|{base['cell_id']}|{_format_storage(after)}"
                ),
                "synthetic_source_id": SYNTHETIC_SOURCE,
                "provenance_class": SYNTHETIC_EVIDENCE,
                "mutation_rule": "one_published_unit",
            }
            if Decimal(row["before_value_decimal"]) == Decimal(row["after_value_decimal"]):
                raise ValueError("H11 mutation did not change a selected value")
            scenario_rows.append(row)
        selected_cells = {row["cell_id"] for row in scenario_rows}
        if not previous_cells.issubset(selected_cells):
            raise ValueError("H11 sweep scenarios are not nested prefixes")
        if {row["revised_source_id"] for row in scenario_rows} != {scenario["revised_source_id"]}:
            raise ValueError(f"scenario {scenario['scenario_id']} revises more than the frozen source")
        injections.extend(scenario_rows)
        plans.append(
            {
                "scenario_order": scenario["scenario_order"],
                "scenario_id": scenario["scenario_id"],
                "seed": seed,
                "selection_count": str(count),
                "base_cell_count": str(len(universe)),
                "selection_fraction": f"{Decimal(count) / Decimal(len(universe)):.6f}",
                "selected_rank_min": "1",
                "selected_rank_max": str(count),
                "synthetic_vintage_id": synthetic_vintage_id,
                "workload_sha256": _payload_hash(scenario_rows),
                "profile_status": scenario["profile_status"],
                "nested_from_previous": "yes" if previous_cells else "not_applicable",
            }
        )
        previous_cells = selected_cells
    return plans, injections


def build_scenario_expectations(
    *,
    plans: list[dict[str, str]],
    injections: list[dict[str, str]],
    injections_path: str,
    injections_sha: str,
    vintages: list[dict[str, str]],
    observations: list[dict[str, str]],
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    scores: list[dict[str, str]],
    baseline: dict[str, Any],
    selection_contract_version: str,
    selection_run_id: str,
    run_id: str,
) -> dict[str, list[dict[str, str]]]:
    """Predict what every treatment must serve, recall and propagate per sweep point."""
    observation_by_id = {row["observation_id"]: row for row in observations}
    panel_orders = arrival_order(vintages)
    baseline_serving = {
        treatment: {row["cell_id"]: row for row in baseline[treatment]["serving"]}
        for treatment in TREATMENTS
    }
    baseline_rows = {
        "B0": len(baseline["B0"]["serving"]),
        "B1": len(baseline["B1"]["states"]),
        "B2": len(baseline["B2"]["serving"]),
        "B3": len(baseline["B3"]["store"]) + len(baseline["B3"]["serving"]),
    }
    panel_cells = len({row["cell_id"] for row in observations})

    synthetic_vintages: list[dict[str, str]] = []
    synthetic_store: list[dict[str, str]] = []
    dirty_rows: list[dict[str, str]] = []
    scenario_rows: list[dict[str, str]] = []
    expected_revised: list[dict[str, str]] = []
    expected_recall: list[dict[str, str]] = []

    for plan in sorted(plans, key=lambda row: int(row["scenario_order"])):
        scenario_id = plan["scenario_id"]
        order = plan["scenario_order"]
        payload = [row for row in injections if row["scenario_id"] == scenario_id]
        count = int(plan["selection_count"])
        if len(payload) != count or _payload_hash(payload) != plan["workload_sha256"]:
            raise ValueError(f"H11 payload of {scenario_id} does not match its plan")

        vintage = {
            **synthetic_vintage_row(
                vintages,
                {"scenario_id": scenario_id, "synthetic_vintage_id": plan["synthetic_vintage_id"]},
                manifest_path=injections_path,
                manifest_sha=injections_sha,
                label_prefix="H11",
            ),
            "arrival_order": SYNTHETIC_ARRIVAL_ORDER,
        }
        synthetic_vintages.append(
            {
                "scenario_order": order,
                "scenario_id": scenario_id,
                **vintage,
                "snapshot_order": SYNTHETIC_SNAPSHOT_ORDER,
                "state_snapshot_key": _id(
                    "H11", "b1_state", vintage["vintage_id"], SYNTHETIC_SNAPSHOT_ORDER
                ),
            }
        )
        synthetic = synthetic_observations(
            payload,
            observation_by_id,
            artifact_path=injections_path,
            artifact_sha=injections_sha,
            run_id=run_id,
            batch_prefix="h11",
            transformation_version=TRANSFORMATION_VERSION,
        )
        payload_by_cell = {row["cell_id"]: row for row in payload}
        for row in sorted(synthetic, key=lambda item: item["observation_id"]):
            injection = payload_by_cell[row["cell_id"]]
            synthetic_store.append(
                {
                    "scenario_order": order,
                    "scenario_id": scenario_id,
                    **row,
                    "source_id": SYNTHETIC_SOURCE,
                    "vintage_date": vintage["vintage_date"],
                    "vintage_retrieved_at": vintage["retrieved_at"],
                    "arrival_order": SYNTHETIC_ARRIVAL_ORDER,
                    "revised_source_id": injection["revised_source_id"],
                    "base_observation_id": injection["base_observation_id"],
                    "base_vintage_id": injection["base_vintage_id"],
                    "snapshot_order": SYNTHETIC_SNAPSHOT_ORDER,
                }
            )

        scenario_vintages = [*vintages, vintage]
        scenario_observations = [*observations, *synthetic]
        scenario_nodes, scenario_edges = synthetic_lineage(nodes, edges, payload, tag="H11")
        impact = lineage_impact_index(scenario_nodes, scenario_edges)
        scoring_source_by_observation = {
            row["synthetic_observation_id"]: row["revised_source_id"] for row in payload
        }
        executed = execute_panel_treatments(
            vintages=scenario_vintages,
            observations=scenario_observations,
            nodes=scenario_nodes,
            edges=scenario_edges,
            scores=scores,
            scoring_source_by_observation=scoring_source_by_observation,
            selection_contract_version=selection_contract_version,
            selection_run_id=selection_run_id,
        )

        for injection in sorted(payload, key=lambda row: int(row["selection_rank"])):
            edge = impact[injection["synthetic_observation_id"]]
            if edge["cell_id"] != injection["cell_id"]:
                raise ValueError("H11 lineage maps a synthetic revision to another cell")
            dirty_rows.append(
                {
                    "scenario_order": order,
                    "scenario_id": scenario_id,
                    "cell_id": injection["cell_id"],
                    "base_observation_id": injection["base_observation_id"],
                    "synthetic_observation_id": injection["synthetic_observation_id"],
                    "lineage_edge_id": edge["lineage_edge_id"],
                    "impact_basis": f"inherited H6C {IMPACT_RELATIONSHIP} edge of the base observation",
                }
            )
        arrivals = executed["B3"]["arrivals"]
        if len(arrivals) != PANEL_ARRIVALS + 1:
            raise ValueError("H11 expected one synthetic arrival after the four panel releases")
        if int(arrivals[-1]["recomputed_cells"]) != count:
            raise ValueError(f"B3 recomputed other than {count} cells for {scenario_id}")

        revised_cells = {row["cell_id"] for row in payload}
        synthetic_ids = {row["observation_id"] for row in synthetic}
        official_ids = {row["observation_id"] for row in observations}
        scenario_row = {
            "scenario_order": order,
            "scenario_id": scenario_id,
            "cells_revised": str(count),
            "selection_share": plan["selection_fraction"],
            "seed": plan["seed"],
            "revised_source_id": sorted({row["revised_source_id"] for row in payload})[0],
            "synthetic_vintage_id": plan["synthetic_vintage_id"],
            "synthetic_vintage_date": vintage["vintage_date"],
            "workload_sha256": plan["workload_sha256"],
            "nested_from_previous": plan["nested_from_previous"],
            "panel_observations": str(len(observations)),
            "panel_cells": str(panel_cells),
            "requests": str(len(observations) + count),
        }
        for treatment in TREATMENTS:
            served = {row["cell_id"]: row for row in executed[treatment]["serving"]}
            addressable = executed[treatment]["addressable"]
            changed = sum(
                1
                for cell_id, row in served.items()
                if row["observation_id"] != baseline_serving[treatment][cell_id]["observation_id"]
            )
            propagated = sum(
                1 for cell_id in revised_cells if served[cell_id]["observation_id"] in synthetic_ids
            )
            if treatment == "B1":
                rows_after = len(executed["B1"]["states"])
                cells_evaluated = panel_cells
                rows_written = rows_after
                snapshots = str(PANEL_ARRIVALS + 1)
            elif treatment == "B2":
                rows_after = len(executed["B2"]["serving"])
                cells_evaluated = panel_cells
                rows_written = panel_cells
                snapshots = "1"
            elif treatment == "B0":
                rows_after = len(executed["B0"]["serving"])
                cells_evaluated = count
                rows_written = count
                snapshots = "1"
            else:
                rows_after = len(executed["B3"]["store"]) + len(executed["B3"]["serving"])
                cells_evaluated = count
                rows_written = count * 2
                snapshots = "1"
            recalled = len(addressable & official_ids) + len(addressable & synthetic_ids)
            scenario_row.update(
                {
                    f"{treatment.lower()}_expected_rows": str(rows_after),
                    f"{treatment.lower()}_expected_cells": str(len(served)),
                    f"{treatment.lower()}_cells_evaluated": str(cells_evaluated),
                    f"{treatment.lower()}_rows_written_logical": str(rows_written),
                    f"{treatment.lower()}_cells_changed": str(changed),
                    f"{treatment.lower()}_propagated_revisions": str(propagated),
                    f"{treatment.lower()}_expected_recalled": str(recalled),
                    f"{treatment.lower()}_expected_snapshots": snapshots,
                }
            )
            if rows_after < baseline_rows[treatment] and treatment != "B0":
                raise ValueError(f"{treatment} lost rows while applying {scenario_id}")

            for injection in sorted(payload, key=lambda row: int(row["selection_rank"])):
                cell_id = injection["cell_id"]
                row = served[cell_id]
                is_synthetic = row["observation_id"] in synthetic_ids
                expected_revised.append(
                    {
                        "scenario_order": order,
                        "scenario_id": scenario_id,
                        "treatment_id": treatment,
                        "selection_rank": injection["selection_rank"],
                        "cell_id": cell_id,
                        "revised_observation_id": injection["synthetic_observation_id"],
                        "revised_value_lexeme": injection["after_value_lexeme"],
                        "served_observation_id": row["observation_id"],
                        "served_value_lexeme": row["value_lexeme"],
                        "revision_served": "yes" if is_synthetic else "no",
                        "base_value_recallable": (
                            "yes" if injection["base_observation_id"] in addressable else "no"
                        ),
                    }
                )
            expected_recall.append(
                {
                    "scenario_order": order,
                    "scenario_id": scenario_id,
                    "treatment_id": treatment,
                    "request_kind": "official",
                    "requests": str(len(official_ids)),
                    "expected_addressable": str(len(addressable & official_ids)),
                    "expected_unavailable": str(len(official_ids - addressable)),
                }
            )
            expected_recall.append(
                {
                    "scenario_order": order,
                    "scenario_id": scenario_id,
                    "treatment_id": treatment,
                    "request_kind": "synthetic",
                    "requests": str(count),
                    "expected_addressable": str(len(addressable & synthetic_ids)),
                    "expected_unavailable": str(len(synthetic_ids - addressable)),
                }
            )
        scenario_rows.append(scenario_row)

    return {
        "vintages": synthetic_vintages,
        "store": synthetic_store,
        "dirty": dirty_rows,
        "scenarios": scenario_rows,
        "revised": expected_revised,
        "recall": expected_recall,
    }


def _manifest_entry(path: Path, rows: int | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": str(path), "sha256": _sha256(path)}
    if rows is not None:
        entry["rows"] = rows
    return entry


def run_prepare(
    *,
    contract_path: Path,
    decisions_path: Path,
    freeze_path: Path,
    scenarios_path: Path,
    universe_path: Path,
    panel_path: Path,
    scores_path: Path,
    b2_contract_path: Path,
    panel_vintages_output: Path,
    panel_observations_output: Path,
    duplicates_output: Path,
    impact_edges_output: Path,
    b1_catalog_output: Path,
    baseline_output: Path,
    plans_output: Path,
    injections_output: Path,
    synthetic_output: Path,
    synthetic_vintages_output: Path,
    dirty_output: Path,
    scenarios_output: Path,
    expected_revised_output: Path,
    expected_recall_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_human_decisions(_read_csv(decisions_path))
    freeze_rows = _read_csv(freeze_path)
    verify_freeze(freeze_rows, contract["freeze"]["required_freeze_ids"])

    panel_config = contract["panel"]
    if str(panel_path) != panel_config["source"]:
        raise ValueError("H11 must read the panel from the frozen F2.3 evidence file")
    publication_manifest_path = Path(panel_config["publication_manifest"])
    publication_catalog = json.loads(publication_manifest_path.read_text(encoding="utf-8"))
    webapi_catalogs = {
        dataset: (Path(path), json.loads(Path(path).read_text(encoding="utf-8")))
        for dataset, path in panel_config["webapi_manifest_by_dataset"].items()
    }
    publication_sources = {item["source_id"] for item in publication_catalog["files"]}

    def retrieved_at_for(row: dict[str, str]) -> str:
        if row["source_id"] in publication_sources:
            return publication_catalog["retrieved_at"]
        dataset = row["input_dataset"]
        if dataset not in webapi_catalogs:
            raise ValueError(f"H11 has no WebAPI manifest for dataset {dataset}")
        return webapi_catalogs[dataset][1]["retrieved_at"]

    panel_rows = _read_csv(panel_path)
    if len(panel_rows) != panel_config["input_rows"]:
        raise ValueError("the H4 panel no longer has the frozen number of rows")
    if {row["ingestion_batch_id"] for row in panel_rows} != {panel_config["batch_id"]}:
        raise ValueError("the panel must come from the frozen H4 ingestion batch")
    kept, duplicates = deduplicate_panel(panel_rows, retrieved_at_for=retrieved_at_for)
    if len(duplicates) != panel_config["deduplication"]["dropped_rows"]:
        raise ValueError("H11 dropped a different number of duplicates than the freeze records")

    vintages, observations = project_panel(
        kept,
        publication_catalog=publication_catalog,
        publication_manifest_path=publication_manifest_path,
        webapi_catalogs=webapi_catalogs,
        webapi_variable_pattern=WEBAPI_VAR,
        batch_id=panel_config["batch_id"],
        run_id="h11-panel-" + _id(_sha256(panel_path), _sha256(contract_path)),
    )
    if len(observations) != panel_config["observations"] or len(vintages) != panel_config["vintages"]:
        raise ValueError("the projected panel does not match the frozen panel shape")
    cells = {row["cell_id"] for row in observations}
    if len(cells) != panel_config["cells"]:
        raise ValueError("the projected panel does not cover the frozen number of cells")
    orders = arrival_order(vintages)
    vintages = [{**row, "arrival_order": str(orders[row["vintage_id"]])} for row in vintages]

    nodes, edges, _, _ = build_lineage(vintages, observations)
    impact = lineage_impact_index(nodes, edges)
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    impact_rows = [
        {
            "edge_id": impact[row["observation_id"]]["lineage_edge_id"],
            "observation_id": row["observation_id"],
            "cell_id": row["cell_id"],
            "vintage_id": row["vintage_id"],
            "source_id": vintage_by_id[row["vintage_id"]]["source_id"],
            "arrival_order": vintage_by_id[row["vintage_id"]]["arrival_order"],
            "relationship": IMPACT_RELATIONSHIP,
        }
        for row in sorted(observations, key=lambda item: (item["cell_id"], item["vintage_id"]))
    ]

    scores = _read_csv(scores_path)
    b2_contract = json.loads(b2_contract_path.read_text(encoding="utf-8"))
    selection_run_id = "h11-" + _id(_sha256(contract_path), _sha256(panel_path))
    baseline = execute_panel_treatments(
        vintages=vintages,
        observations=observations,
        nodes=nodes,
        edges=edges,
        scores=scores,
        scoring_source_by_observation={},
        selection_contract_version=b2_contract["contract_version"],
        selection_run_id=selection_run_id,
    )

    base_by_cell = {row["cell_id"]: row for row in baseline["B0"]["serving"]}
    source_by_vintage = {row["vintage_id"]: row["source_id"] for row in vintages}
    plans, injections = build_sweep_payload(
        scenarios=_read_csv(scenarios_path),
        universe=_read_csv(universe_path),
        base_by_cell=base_by_cell,
        source_by_vintage=source_by_vintage,
        contract_universe=contract["universe"],
    )
    _write_csv(injections_output, INJECTION_COLUMNS, injections)

    expectations = build_scenario_expectations(
        plans=plans,
        injections=injections,
        injections_path=str(injections_output),
        injections_sha=_sha256(injections_output),
        vintages=vintages,
        observations=observations,
        nodes=nodes,
        edges=edges,
        scores=scores,
        baseline=baseline,
        selection_contract_version=b2_contract["contract_version"],
        selection_run_id=selection_run_id,
        run_id=selection_run_id,
    )

    b2_by_source: dict[str, int] = {}
    for row in baseline["B2"]["serving"]:
        b2_by_source[row["selected_source_id"]] = b2_by_source.get(row["selected_source_id"], 0) + 1
    baseline_rows = [
        {
            "treatment_id": "B0",
            "table": contract["tables"]["B0"][0],
            "expected_rows": str(len(baseline["B0"]["serving"])),
            "expected_cells": str(len(cells)),
            "expected_snapshots": "1",
            "load_statements": str(PANEL_ARRIVALS),
            "detail": "one MERGE per arriving vintage, then expire_snapshots down to one",
        },
        {
            "treatment_id": "B1",
            "table": contract["tables"]["B1"][0],
            "expected_rows": str(len(baseline["B1"]["states"])),
            "expected_cells": str(len(cells)),
            "expected_snapshots": str(PANEL_ARRIVALS),
            "load_statements": str(PANEL_ARRIVALS),
            "detail": ";".join(
                f"state_{row['snapshot_order']}={row['state_rows']}" for row in baseline["B1"]["catalog"]
            ),
        },
        {
            "treatment_id": "B2",
            "table": contract["tables"]["B2"][0],
            "expected_rows": str(len(baseline["B2"]["serving"])),
            "expected_cells": str(len(cells)),
            "expected_snapshots": "1",
            "load_statements": "1",
            "detail": ";".join(f"{source}={count}" for source, count in sorted(b2_by_source.items())),
        },
        {
            "treatment_id": "B3",
            "table": contract["tables"]["B3"][0],
            "expected_rows": str(len(baseline["B3"]["store"])),
            "expected_cells": str(len(cells)),
            "expected_snapshots": "1",
            "load_statements": str(PANEL_ARRIVALS),
            "detail": "append-only store keyed by (cell_id, vintage_id)",
        },
        {
            "treatment_id": "B3",
            "table": contract["tables"]["B3"][1],
            "expected_rows": str(len(baseline["B3"]["serving"])),
            "expected_cells": str(len(cells)),
            "expected_snapshots": "1",
            "load_statements": str(PANEL_ARRIVALS),
            "detail": ";".join(
                f"arrival_{row['arrival_order']}={row['recomputed_cells']}"
                for row in baseline["B3"]["arrivals"]
            ),
        },
    ]

    written = [_manifest_entry(injections_output, len(injections))]
    for path, columns, rows in (
        (panel_vintages_output, PANEL_VINTAGE_COLUMNS, vintages),
        (panel_observations_output, OBSERVATION_COLUMNS, observations),
        (duplicates_output, DUPLICATE_COLUMNS, duplicates),
        (impact_edges_output, IMPACT_EDGE_COLUMNS, impact_rows),
        (b1_catalog_output, B1_CATALOG_COLUMNS, baseline["B1"]["catalog"]),
        (baseline_output, BASELINE_COLUMNS, baseline_rows),
        (plans_output, PLAN_COLUMNS, plans),
        (synthetic_output, SYNTHETIC_STORE_COLUMNS, expectations["store"]),
        (synthetic_vintages_output, SYNTHETIC_VINTAGE_COLUMNS, expectations["vintages"]),
        (dirty_output, DIRTY_CELL_COLUMNS, expectations["dirty"]),
        (scenarios_output, SCENARIO_COLUMNS, expectations["scenarios"]),
        (expected_revised_output, EXPECTED_REVISED_COLUMNS, expectations["revised"]),
        (expected_recall_output, EXPECTED_RECALL_COLUMNS, expectations["recall"]),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    manifest = {
        "stage": "H11",
        "track": "B",
        "contract_version": contract["contract_version"],
        "payload_status": "prepared",
        "panel": {
            "input_rows": len(panel_rows),
            "observations": len(observations),
            "cells": len(cells),
            "vintages": len(vintages),
            "dropped_duplicates": len(duplicates),
            "lineage_nodes": len(nodes),
            "lineage_edges": len(edges),
            "impact_edges": len(impact_rows),
        },
        "baseline": {row["table"]: row["expected_rows"] for row in baseline_rows},
        "selection": {
            "contract_version": b2_contract["contract_version"],
            "run_id": selection_run_id,
        },
        "arrivals": PANEL_ARRIVALS,
        "tables": contract["tables"],
        "scenarios": [
            {
                key: row[key]
                for key in (
                    "scenario_order",
                    "scenario_id",
                    "cells_revised",
                    "workload_sha256",
                    "synthetic_vintage_id",
                )
            }
            for row in expectations["scenarios"]
        ],
        "inputs": [
            _manifest_entry(path)
            for path in (
                contract_path,
                decisions_path,
                freeze_path,
                scenarios_path,
                universe_path,
                panel_path,
                scores_path,
                b2_contract_path,
                publication_manifest_path,
                *[path for path, _ in webapi_catalogs.values()],
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
        "observations": len(observations),
        "cells": len(cells),
        "vintages": len(vintages),
        "duplicates": len(duplicates),
        "scenarios": len(expectations["scenarios"]),
        "injections": len(injections),
        "baseline_rows": {row["table"]: row["expected_rows"] for row in baseline_rows},
    }


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
    "scenario_order",
    "scenario_id",
    "cells_revised",
    "selection_share",
    "treatment_id",
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
    "recall_rate",
    "propagation_rate",
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
    "baseline_data_bytes",
    "after_data_bytes",
    "baseline_rows",
    "after_rows",
    "baseline_snapshots",
    "after_snapshots",
]
RECALL_COLUMNS = [
    "scenario_id",
    "treatment_id",
    "request_kind",
    "requests",
    "addressable",
    "exact",
    "expected_addressable",
    "recall_rate",
    "repetitions_agreeing",
]
PROPAGATION_COLUMNS = [
    "scenario_id",
    "cells_revised",
    "treatment_id",
    "admitted_revisions",
    "served_revisions",
    "expected_served_revisions",
    "propagation_rate",
]
BREAKEVEN_COLUMNS = [
    "comparison",
    "measure",
    "incremental_treatment",
    "comparator_treatment",
    "cheaper_at_smallest_point",
    "crossing_cells",
    "crossing_share",
    "direction",
    "detail",
]
INJECTION_COLUMNS_OUT = [
    "repetition",
    "scenario_id",
    "treatment_id",
    "served_rows",
    "served_cells",
    "snapshots",
    "state_mismatches",
    "served_revisions",
]


def _lines(path: Path, prefix: str) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix + "|"):
            rows.append(line.split("|"))
    return rows


def _median_int(values: list[int]) -> int:
    return int(statistics.median(values))


def _median_seconds(values: list[float]) -> str:
    return f"{statistics.median(values):.3f}"


def read_environment(path: Path) -> dict[str, str]:
    environment = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        environment[key] = value
    return environment


def audit_timing(
    lines: list[list[str]], *, repetitions: int, scenarios: list[str]
) -> list[dict[str, str]]:
    expected_labels = {
        "B0": ["merge_revision", "expire_snapshots", "verify_state"],
        "B1": ["insert_overwrite_all_states", "verify_state"],
        "B2": ["insert_overwrite_selection", "expire_snapshots", "verify_state"],
        "B3": [
            "insert_store_rows",
            "merge_serving_dirty_cells",
            "expire_snapshots_store",
            "expire_snapshots_serving",
            "verify_state",
        ],
    }
    rows: list[dict[str, str]] = []
    seen: dict[tuple[str, str, str], list[str]] = {}
    for _, rep, scenario, treatment, index, label, phase, seconds in lines:
        if int(rep) < 1 or int(rep) > repetitions or scenario not in scenarios:
            raise ValueError(f"unexpected H11 timing row for rep {rep} {scenario}")
        if treatment not in TREATMENTS or phase not in {"harness", "write", "maintenance", "verification"}:
            raise ValueError(f"unexpected H11 timing row for {treatment} phase {phase}")
        float(seconds)
        if label != "staging_views":
            seen.setdefault((rep, scenario, treatment), []).append(label)
        rows.append(
            {
                "repetition": rep,
                "scenario_id": scenario,
                "treatment_id": treatment,
                "statement_index": index,
                "statement_label": label,
                "phase": phase,
                "seconds": seconds,
            }
        )
    for rep in range(1, repetitions + 1):
        for scenario in scenarios:
            for treatment in TREATMENTS:
                labels = seen.get((str(rep), scenario, treatment))
                if labels != expected_labels[treatment]:
                    raise ValueError(
                        f"H11 {treatment} in rep {rep} {scenario} did not issue its frozen statements"
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
            raise ValueError(f"unexpected H11 footprint row for {treatment} {table} rep {rep}")
        if phase not in PHASES or object_class not in CLASSES:
            raise ValueError(f"unexpected H11 footprint phase {phase} or class {object_class}")
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
                        raise ValueError(
                            f"H11 has no {phase} measurement for {table} rep {rep} {scenario}"
                        )
                    objects = reachable[key]
                    phase_values[phase] = {
                        "objects": len(objects),
                        "bytes": sum(size for size, _ in objects.values()),
                        "data_bytes": sum(
                            size
                            for size, object_class in objects.values()
                            if object_class in {"data", "delete"}
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
                        "baseline_data_bytes": str(baseline["data_bytes"]),
                        "after_data_bytes": str(after["data_bytes"]),
                        "baseline_rows": baseline["rows"],
                        "after_rows": after["rows"],
                        "baseline_snapshots": baseline["snapshots"],
                        "after_snapshots": after["snapshots"],
                    }
                )
    return rows


def audit_injection(
    *, lines: list[list[str]], repetitions: int, expectations: list[dict[str, str]]
) -> list[dict[str, str]]:
    by_scenario = {row["scenario_id"]: row for row in expectations}
    rows: list[dict[str, str]] = []
    seen = set()
    for _, rep, scenario, treatment, served_rows, cells, snapshots, mismatches, propagated, _extra in lines:
        if int(rep) < 1 or int(rep) > repetitions or scenario not in by_scenario:
            raise ValueError(f"unexpected H11 injection row for rep {rep} {scenario}")
        if treatment not in TREATMENTS:
            raise ValueError(f"unexpected H11 injection row for treatment {treatment}")
        if (rep, scenario, treatment) in seen:
            raise ValueError(f"H11 injected {treatment} twice in rep {rep} {scenario}")
        seen.add((rep, scenario, treatment))
        expectation = by_scenario[scenario]
        if mismatches != "0":
            raise ValueError(
                f"H11 {treatment} state after {scenario} differs from the predicted state"
            )
        if cells != expectation[f"{treatment.lower()}_expected_cells"]:
            raise ValueError(f"H11 {treatment} serves {cells} cells after {scenario}")
        if snapshots != expectation[f"{treatment.lower()}_expected_snapshots"]:
            raise ValueError(f"H11 {treatment} retains {snapshots} snapshots after {scenario}")
        if treatment == "B3":
            expected_rows = str(
                int(expectation["panel_observations"]) + int(expectation["cells_revised"])
            )
        else:
            expected_rows = expectation[f"{treatment.lower()}_expected_rows"]
        if served_rows != expected_rows:
            raise ValueError(
                f"H11 {treatment} holds {served_rows} rows after {scenario} instead of {expected_rows}"
            )
        if propagated != expectation[f"{treatment.lower()}_propagated_revisions"]:
            raise ValueError(f"H11 {treatment} propagated {propagated} revisions after {scenario}")
        rows.append(
            {
                "repetition": rep,
                "scenario_id": scenario,
                "treatment_id": treatment,
                "served_rows": served_rows,
                "served_cells": cells,
                "snapshots": snapshots,
                "state_mismatches": mismatches,
                "served_revisions": propagated,
            }
        )
    if len(seen) != repetitions * len(by_scenario) * len(TREATMENTS):
        raise ValueError("H11 did not inject every treatment in every repetition and scenario")
    return rows


def audit_recall(
    *, lines: list[list[str]], expected: list[dict[str, str]], repetitions: int
) -> list[dict[str, str]]:
    expected_by_key = {
        (row["scenario_id"], row["treatment_id"], row["request_kind"]): row for row in expected
    }
    observed: dict[tuple[str, str, str], list[tuple[int, int, int]]] = {}
    for _, _rep, scenario, treatment, kind, requests, addressable, exact in lines:
        key = (scenario, treatment, kind)
        if key not in expected_by_key:
            raise ValueError(f"H11 recalled an unexpected request class {key}")
        if addressable != exact:
            raise ValueError(
                f"H11 {treatment} returned a different value than published for {scenario} {kind}"
            )
        observed.setdefault(key, []).append((int(requests), int(addressable), int(exact)))

    rows: list[dict[str, str]] = []
    for key, expectation in sorted(expected_by_key.items()):
        measurements = observed.get(key)
        if measurements is None or len(measurements) != repetitions:
            raise ValueError(f"H11 recall for {key} was not measured in every repetition")
        if len(set(measurements)) != 1:
            raise ValueError(f"H11 recall for {key} differs between repetitions")
        requests, addressable, exact = measurements[0]
        if requests != int(expectation["requests"]) or addressable != int(
            expectation["expected_addressable"]
        ):
            raise ValueError(
                f"H11 recall for {key} is {addressable}/{requests} instead of the predicted "
                f"{expectation['expected_addressable']}/{expectation['requests']}"
            )
        rows.append(
            {
                "scenario_id": key[0],
                "treatment_id": key[1],
                "request_kind": key[2],
                "requests": str(requests),
                "addressable": str(addressable),
                "exact": str(exact),
                "expected_addressable": expectation["expected_addressable"],
                "recall_rate": f"{Decimal(exact) / Decimal(requests):.4f}" if requests else "",
                "repetitions_agreeing": str(len(measurements)),
            }
        )
    return rows


def aggregate_apply_cost(
    *,
    timing_rows: list[dict[str, str]],
    storage_rows: list[dict[str, str]],
    injection_rows: list[dict[str, str]],
    recall_rows: list[dict[str, str]],
    expectations: list[dict[str, str]],
    contract: dict[str, Any],
) -> list[dict[str, str]]:
    by_scenario = {row["scenario_id"]: row for row in expectations}
    ordered_scenarios = sorted(by_scenario.values(), key=lambda row: int(row["scenario_order"]))

    seconds: dict[tuple[str, str, str, str], float] = {}
    for row in timing_rows:
        if row["phase"] not in {"write", "maintenance"}:
            continue
        key = (row["scenario_id"], row["treatment_id"], row["repetition"], row["phase"])
        seconds[key] = seconds.get(key, 0.0) + float(row["seconds"])
    write_statements: dict[tuple[str, str], int] = {}
    for row in timing_rows:
        if row["phase"] != "write":
            continue
        key = (row["scenario_id"], row["treatment_id"])
        write_statements[key] = write_statements.get(key, 0) + 1

    deltas: dict[tuple[str, str, str], dict[str, int]] = {}
    for row in storage_rows:
        key = (row["scenario_id"], row["treatment_id"], row["repetition"])
        entry = deltas.setdefault(
            key, {"baseline": 0, "after": 0, "delta": 0, "delta_data": 0}
        )
        entry["baseline"] += int(row["baseline_bytes"])
        entry["after"] += int(row["after_bytes"])
        entry["delta"] += int(row["delta_bytes"])
        entry["delta_data"] += int(row["after_data_bytes"]) - int(row["baseline_data_bytes"])

    snapshots = {
        (row["scenario_id"], row["treatment_id"]): row["snapshots"] for row in injection_rows
    }
    served = {
        (row["scenario_id"], row["treatment_id"]): row["served_revisions"] for row in injection_rows
    }
    recall_totals: dict[tuple[str, str], tuple[int, int]] = {}
    for row in recall_rows:
        key = (row["scenario_id"], row["treatment_id"])
        requests, exact = recall_totals.get(key, (0, 0))
        recall_totals[key] = (requests + int(row["requests"]), exact + int(row["exact"]))

    repetitions = sorted({row["repetition"] for row in timing_rows}, key=int)
    rows: list[dict[str, str]] = []
    for scenario in ordered_scenarios:
        scenario_id = scenario["scenario_id"]
        for treatment in TREATMENTS:
            write_values = [seconds.get((scenario_id, treatment, rep, "write"), 0.0) for rep in repetitions]
            maintenance_values = [
                seconds.get((scenario_id, treatment, rep, "maintenance"), 0.0) for rep in repetitions
            ]
            totals = [write + maintenance for write, maintenance in zip(write_values, maintenance_values)]
            byte_values = [deltas[(scenario_id, treatment, rep)] for rep in repetitions]
            requests, exact = recall_totals[(scenario_id, treatment)]
            admitted = int(scenario["cells_revised"])
            delta_median = _median_int([entry["delta"] for entry in byte_values])
            data_median = _median_int([entry["delta_data"] for entry in byte_values])
            rows.append(
                {
                    "scenario_order": scenario["scenario_order"],
                    "scenario_id": scenario_id,
                    "cells_revised": scenario["cells_revised"],
                    "selection_share": scenario["selection_share"],
                    "treatment_id": treatment,
                    "cells_evaluated": scenario[f"{treatment.lower()}_cells_evaluated"],
                    "rows_written_logical": scenario[f"{treatment.lower()}_rows_written_logical"],
                    "write_statements": str(
                        write_statements[(scenario_id, treatment)] // len(repetitions)
                    ),
                    "write_seconds_median": _median_seconds(write_values),
                    "write_seconds_min": f"{min(write_values):.3f}",
                    "write_seconds_max": f"{max(write_values):.3f}",
                    "maintenance_seconds_median": _median_seconds(maintenance_values),
                    "total_seconds_median": _median_seconds(totals),
                    "baseline_bytes_median": str(_median_int([entry["baseline"] for entry in byte_values])),
                    "after_bytes_median": str(_median_int([entry["after"] for entry in byte_values])),
                    "delta_bytes_median": str(delta_median),
                    "delta_bytes_min": str(min(entry["delta"] for entry in byte_values)),
                    "delta_bytes_max": str(max(entry["delta"] for entry in byte_values)),
                    "delta_data_bytes_median": str(data_median),
                    "delta_metadata_bytes_median": str(delta_median - data_median),
                    "snapshots_after": snapshots[(scenario_id, treatment)],
                    "recall_rate": f"{Decimal(exact) / Decimal(requests):.4f}",
                    "propagation_rate": (
                        f"{Decimal(served[(scenario_id, treatment)]) / Decimal(admitted):.4f}"
                        if admitted
                        else ""
                    ),
                }
            )
    return rows


def find_breakeven(
    cost_rows: list[dict[str, str]], comparisons: list[str], measures: list[str]
) -> list[dict[str, str]]:
    """Report the smallest swept size at which the incremental treatment stops winning.

    Nothing is interpolated: only the frozen sweep sizes are reported, and a sweep that
    never crosses is reported as a direction that holds over the whole range.
    """
    by_key = {(row["scenario_id"], row["treatment_id"]): row for row in cost_rows}
    sizes = sorted(
        {(int(row["cells_revised"]), row["scenario_id"], row["selection_share"]) for row in cost_rows}
    )
    rows: list[dict[str, str]] = []
    for comparison in comparisons:
        incremental, comparator = [part.strip() for part in comparison.split("against")]
        for measure in measures:
            values = []
            for cells, scenario_id, share in sizes:
                left = Decimal(by_key[(scenario_id, incremental)][measure])
                right = Decimal(by_key[(scenario_id, comparator)][measure])
                values.append((cells, share, left, right))
            cheaper = [left < right for _, _, left, right in values]
            crossing_cells = "none"
            crossing_share = ""
            if cheaper[0]:
                for index, is_cheaper in enumerate(cheaper):
                    if not is_cheaper:
                        crossing_cells = str(values[index][0])
                        crossing_share = values[index][1]
                        break
            if all(cheaper):
                direction = f"{incremental}_cheaper_over_the_whole_sweep"
            elif not any(cheaper):
                direction = f"{comparator}_cheaper_over_the_whole_sweep"
            elif cheaper[0]:
                direction = f"{incremental}_cheaper_until_{crossing_cells}_cells"
            else:
                direction = "mixed_without_a_single_crossing"
            rows.append(
                {
                    "comparison": comparison,
                    "measure": measure,
                    "incremental_treatment": incremental,
                    "comparator_treatment": comparator,
                    "cheaper_at_smallest_point": "yes" if cheaper[0] else "no",
                    "crossing_cells": crossing_cells,
                    "crossing_share": crossing_share,
                    "direction": direction,
                    "detail": ";".join(
                        f"{cells}:{left}/{right}" for cells, _, left, right in values
                    ),
                }
            )
    return rows


def build_validation(
    *,
    contract: dict[str, Any],
    environment: dict[str, str],
    freeze_rows: list[dict[str, str]],
    baseline_markers: list[str],
    injection_rows: list[dict[str, str]],
    recall_rows: list[dict[str, str]],
    storage_rows: list[dict[str, str]],
    timing_rows: list[dict[str, str]],
    verification_lines: list[list[str]],
    expectations: list[dict[str, str]],
    panel_rows: int,
    panel_cells: int,
) -> list[dict[str, str]]:
    repetitions = contract["protocol"]["repetitions"]
    scenarios = [row["scenario_id"] for row in expectations]
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
        f"{len(freeze_rows)} frozen items re-checked against config/experiments/experiment_freeze.csv",
    )
    add(
        "the panel keeps its frozen shape",
        panel_rows == contract["panel"]["observations"] and panel_cells == contract["panel"]["cells"],
        panel_rows,
        f"{panel_rows} observations over {panel_cells} cells",
    )
    add(
        "every baseline rebuild reproduces the same treatment state",
        len(set(baseline_markers)) == 1 and len(baseline_markers) == repetitions * len(scenarios),
        len(baseline_markers),
        f"{len(baseline_markers)} rebuilds, {len(set(baseline_markers))} distinct marker",
    )
    add(
        "every post-revision state equals the predicted state",
        all(row["state_mismatches"] == "0" for row in injection_rows),
        len(injection_rows),
        "cells the scenario revises are checked against the frozen prediction, the rest against the panel state",
    )
    add(
        "recall equals the predicted recall in every repetition",
        all(row["repetitions_agreeing"] == str(repetitions) for row in recall_rows),
        len(recall_rows),
        "official and synthetic requests, matched on observation_id and value_lexeme",
    )
    add(
        "revision propagation equals the prediction",
        all(
            row["served_revisions"]
            == next(
                item[f"{row['treatment_id'].lower()}_propagated_revisions"]
                for item in expectations
                if item["scenario_id"] == row["scenario_id"]
            )
            for row in injection_rows
        ),
        len(injection_rows),
        "served revisions counted in the serving state of each treatment",
    )
    b1_snapshots = {
        row["snapshots"] for row in injection_rows if row["treatment_id"] == "B1"
    }
    other_snapshots = {
        row["snapshots"] for row in injection_rows if row["treatment_id"] != "B1"
    }
    add(
        "B1 retains one snapshot per release plus the revision while the others retain one",
        b1_snapshots == {str(PANEL_ARRIVALS + 1)} and other_snapshots == {"1"},
        len(injection_rows),
        f"B1 {sorted(b1_snapshots)}, others {sorted(other_snapshots)}",
    )
    previous_rows = [row for row in verification_lines if row[3] == "b1_previous_snapshot_rows"]
    baseline_b1 = next(
        int(row["baseline_rows"])
        for row in storage_rows
        if row["treatment_id"] == "B1"
    )
    add(
        "the B1 snapshot before the revision still holds the pre-revision state",
        all(int(row[4]) == baseline_b1 and row[5] == "0" for row in previous_rows),
        len(previous_rows),
        f"VERSION AS OF returns {baseline_b1} rows and no revised state",
    )
    add(
        "every metadata-referenced object exists in MinIO with the size metadata records",
        True,
        len(storage_rows),
        "checked while folding the footprint rows",
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
        f"commit {environment.get('git_commit')}, dirty entries {environment.get('git_dirty_entries')}",
    )
    add(
        "all repetitions are reported before any aggregation",
        len({row["repetition"] for row in timing_rows}) == repetitions,
        len(timing_rows),
        f"{repetitions} repetitions of {len(scenarios)} scenarios and {len(TREATMENTS)} treatments",
    )
    return rows


def build_summary(
    *,
    contract: dict[str, Any],
    environment: dict[str, str],
    cost_rows: list[dict[str, str]],
    breakeven_rows: list[dict[str, str]],
    recall_rows: list[dict[str, str]],
    expectations: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {
            "metric": "repetitions",
            "value": str(contract["protocol"]["repetitions"]),
            "unit": "runs",
            "interpretation": "serial rebuild-inject-measure cycles per sweep point",
        },
        {
            "metric": "sweep_points",
            "value": str(len(expectations)),
            "unit": "scenarios",
            "interpretation": "frozen sizes "
            + "-".join(row["cells_revised"] for row in sorted(expectations, key=lambda item: int(item["scenario_order"]))),
        },
        {
            "metric": "panel_cells",
            "value": expectations[0]["panel_cells"],
            "unit": "cells",
            "interpretation": f"{expectations[0]['panel_observations']} observations of the frozen province panel",
        },
        {
            "metric": "host_nproc",
            "value": environment.get("host_nproc", ""),
            "unit": "vCPU",
            "interpretation": "declared timing environment; comparison between treatments only",
        },
    ]
    for row in cost_rows:
        prefix = f"{row['treatment_id'].lower()}_{row['scenario_id']}"
        rows.append(
            {
                "metric": f"{prefix}_total_seconds_median",
                "value": row["total_seconds_median"],
                "unit": "seconds",
                "interpretation": (
                    f"write {row['write_seconds_median']} (range {row['write_seconds_min']}-"
                    f"{row['write_seconds_max']}) plus maintenance {row['maintenance_seconds_median']} "
                    f"over {row['write_statements']} write statements"
                ),
            }
        )
        rows.append(
            {
                "metric": f"{prefix}_delta_bytes_median",
                "value": row["delta_bytes_median"],
                "unit": "bytes",
                "interpretation": (
                    f"range {row['delta_bytes_min']}-{row['delta_bytes_max']}; data "
                    f"{row['delta_data_bytes_median']}; metadata {row['delta_metadata_bytes_median']}; "
                    f"{row['rows_written_logical']} logical rows written"
                ),
            }
        )
    for row in breakeven_rows:
        rows.append(
            {
                "metric": f"breakeven_{row['incremental_treatment'].lower()}_{row['comparator_treatment'].lower()}_{row['measure']}",
                "value": row["crossing_cells"],
                "unit": "cells",
                "interpretation": f"{row['direction']}; {row['detail']}",
            }
        )
    for row in recall_rows:
        if row["request_kind"] != "official":
            continue
        rows.append(
            {
                "metric": f"{row['treatment_id'].lower()}_{row['scenario_id']}_official_recall",
                "value": row["recall_rate"],
                "unit": "ratio",
                "interpretation": (
                    f"{row['exact']} of {row['requests']} published observations returned with the exact lexeme"
                ),
            }
        )
    return rows


def run_aggregate(
    *,
    contract_path: Path,
    decisions_path: Path,
    freeze_path: Path,
    payload_manifest_path: Path,
    raw_dir: Path,
    timing_output: Path,
    apply_cost_output: Path,
    storage_output: Path,
    recall_output: Path,
    propagation_output: Path,
    injection_output: Path,
    breakeven_output: Path,
    validation_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_human_decisions(_read_csv(decisions_path))
    freeze_rows = _read_csv(freeze_path)
    verify_freeze(freeze_rows, contract["freeze"]["required_freeze_ids"])

    payload = json.loads(payload_manifest_path.read_text(encoding="utf-8"))
    if payload.get("stage") != "H11" or payload.get("payload_status") != "prepared":
        raise ValueError("H11 aggregation needs the prepared payload manifest")
    outputs = {}
    for item in payload["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested payload output {path}")
        outputs[path.name] = path
    expectations = _read_csv(outputs["h11-sweep-scenarios.csv"])
    expected_recall = _read_csv(outputs["h11-expected-recall.csv"])
    panel_observations = _read_csv(outputs["h11-panel-observations.csv"])

    environment = read_environment(raw_dir / "environment.txt")
    repetitions = contract["protocol"]["repetitions"]
    if environment.get("repetitions") != str(repetitions):
        raise ValueError("the raw run did not use the frozen repetition count")
    scenarios = [
        row["scenario_id"]
        for row in sorted(contract["scenarios"], key=lambda item: int(item["scenario_order"]))
    ]
    if environment.get("scenarios") != ";".join(scenarios):
        raise ValueError("the raw run did not cover the frozen sweep scenarios")
    if environment.get("limited_run", "no") != "no":
        raise ValueError("a limited run can never be aggregated as the main sweep")

    timing_rows = audit_timing(
        _lines(raw_dir / "timing.txt", "H11T"), repetitions=repetitions, scenarios=scenarios
    )
    storage_rows = measure_phases(
        contract=contract,
        footprint_lines=_lines(raw_dir / "footprint.txt", "H11F"),
        state_lines=_lines(raw_dir / "footprint.txt", "H11S"),
        listing_lines=_lines(raw_dir / "listing.txt", "H11L"),
        scenarios=scenarios,
    )
    injection_rows = audit_injection(
        lines=_lines(raw_dir / "injection.txt", "H11I"),
        repetitions=repetitions,
        expectations=expectations,
    )
    recall_rows = audit_recall(
        lines=_lines(raw_dir / "recall.txt", "H11R"),
        expected=expected_recall,
        repetitions=repetitions,
    )
    verification_lines = _lines(raw_dir / "recall.txt", "H11V")
    baseline_markers = [
        line.split("|", 2)[2]
        for line in (raw_dir / "baseline-markers.txt").read_text(encoding="utf-8").splitlines()
        if line
    ]

    cost_rows = aggregate_apply_cost(
        timing_rows=timing_rows,
        storage_rows=storage_rows,
        injection_rows=injection_rows,
        recall_rows=recall_rows,
        expectations=expectations,
        contract=contract,
    )
    breakeven_rows = find_breakeven(
        cost_rows, contract["breakeven"]["compared"], contract["breakeven"]["measures"]
    )
    propagation_rows = [
        {
            "scenario_id": row["scenario_id"],
            "cells_revised": row["cells_revised"],
            "treatment_id": row["treatment_id"],
            "admitted_revisions": row["cells_revised"],
            "served_revisions": next(
                item["served_revisions"]
                for item in injection_rows
                if item["scenario_id"] == row["scenario_id"] and item["treatment_id"] == row["treatment_id"]
            ),
            "expected_served_revisions": next(
                item[f"{row['treatment_id'].lower()}_propagated_revisions"]
                for item in expectations
                if item["scenario_id"] == row["scenario_id"]
            ),
            "propagation_rate": row["propagation_rate"],
        }
        for row in cost_rows
    ]
    validation_rows = build_validation(
        contract=contract,
        environment=environment,
        freeze_rows=freeze_rows,
        baseline_markers=baseline_markers,
        injection_rows=injection_rows,
        recall_rows=recall_rows,
        storage_rows=storage_rows,
        timing_rows=timing_rows,
        verification_lines=verification_lines,
        expectations=expectations,
        panel_rows=len(panel_observations),
        panel_cells=len({row["cell_id"] for row in panel_observations}),
    )
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["invariant"] for row in validation_rows if row["status"] != "pass"]
        raise ValueError(f"H11 invariants failed: {failed}")
    summary_rows = build_summary(
        contract=contract,
        environment=environment,
        cost_rows=cost_rows,
        breakeven_rows=breakeven_rows,
        recall_rows=recall_rows,
        expectations=expectations,
    )

    written = []
    for path, columns, rows in (
        (timing_output, TIMING_COLUMNS, timing_rows),
        (apply_cost_output, APPLY_COST_COLUMNS, cost_rows),
        (storage_output, STORAGE_DELTA_COLUMNS, storage_rows),
        (recall_output, RECALL_COLUMNS, recall_rows),
        (propagation_output, PROPAGATION_COLUMNS, propagation_rows),
        (injection_output, INJECTION_COLUMNS_OUT, injection_rows),
        (breakeven_output, BREAKEVEN_COLUMNS, breakeven_rows),
        (validation_output, VALIDATION_COLUMNS, validation_rows),
        (summary_output, SUMMARY_COLUMNS, summary_rows),
    ):
        _write_csv(path, columns, rows)
        written.append(_manifest_entry(path, len(rows)))

    by_key = {(row["scenario_id"], row["treatment_id"]): row for row in cost_rows}
    smallest, largest = scenarios[0], scenarios[-1]
    manifest = {
        "stage": "H11",
        "track": "B",
        "contract_version": contract["contract_version"],
        "execution_status": "executed_physical",
        "environment": environment,
        "apply_cost": {
            f"{row['scenario_id']}|{row['treatment_id']}": {
                key: row[key]
                for key in (
                    "write_seconds_median",
                    "maintenance_seconds_median",
                    "total_seconds_median",
                    "delta_bytes_median",
                    "cells_evaluated",
                    "recall_rate",
                    "propagation_rate",
                )
            }
            for row in cost_rows
        },
        "breakeven": {
            f"{row['incremental_treatment']}|{row['comparator_treatment']}|{row['measure']}": {
                "crossing_cells": row["crossing_cells"],
                "direction": row["direction"],
            }
            for row in breakeven_rows
        },
        "inputs": [
            _manifest_entry(path)
            for path in (contract_path, decisions_path, freeze_path, payload_manifest_path)
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
        "scenarios": len(scenarios),
        "routes": len(injection_rows),
        "panel_observations": len(panel_observations),
        "panel_cells": len({row["cell_id"] for row in panel_observations}),
        "seconds": {
            treatment: {
                "smallest": by_key[(smallest, treatment)]["total_seconds_median"],
                "largest": by_key[(largest, treatment)]["total_seconds_median"],
            }
            for treatment in TREATMENTS
        },
        "delta_bytes": {
            treatment: {
                "smallest": by_key[(smallest, treatment)]["delta_bytes_median"],
                "largest": by_key[(largest, treatment)]["delta_bytes_median"],
            }
            for treatment in TREATMENTS
        },
        "recall": {
            treatment: by_key[(largest, treatment)]["recall_rate"] for treatment in TREATMENTS
        },
        "breakeven": {
            f"{row['incremental_treatment']}|{row['comparator_treatment']}|{row['measure']}": row["crossing_cells"]
            for row in breakeven_rows
        },
        "status": "measured",
    }
