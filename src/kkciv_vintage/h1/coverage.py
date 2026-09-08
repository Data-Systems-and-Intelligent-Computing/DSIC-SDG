from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from .inventory import indicator_paths, read_csv


VARIABLE_COLUMNS = [
    "webapi_domain_id",
    "webapi_variable_id",
    "title",
    "subject_name",
    "vervar_dimension",
    "geography_levels",
    "national_units",
    "province_units",
    "regency_units",
    "category_dimensions",
    "category_count",
    "period_types",
    "period_start",
    "period_end",
    "period_count",
    "period_gaps",
    "observed_cells",
    "expected_cells",
    "cell_density",
    "last_update",
    "producer",
    "indicator_keys",
    "selection_statuses",
]
INDICATOR_COLUMNS = [
    "indicator_key",
    "domain",
    "sdg_code",
    "proposed_geographies",
    "proposed_sources",
    "webapi_domain_id",
    "webapi_variable_ids",
    "verified_geographies",
    "period_start",
    "period_end",
    "period_gaps",
    "observed_cells",
    "last_update",
    "tpb_publication_year",
    "tpb_table_or_page",
    "derived_status",
    "status_reason",
    "derived_risk_flags",
    "producer",
]
GEOGRAPHY_ORDER = ["national", "province", "regency"]
PUBLICATION_SELECTION_STATUSES = {"selected", "selected_limited"}


def _classify_vervar(value: int) -> str:
    """Map a BPS vervar code to a geography level.

    9999 is the national aggregate, four-digit codes ending in 00 are provinces,
    and the remaining four-digit codes are regencies or cities. Codes below 1100
    are not geographies at all; they encode a non-spatial breakdown.
    """
    if value == 9999:
        return "national"
    if value < 1100:
        return "non_spatial"
    return "province" if value % 100 == 0 else "regency"


def _year(label: str) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", str(label))
    return int(match.group()) if match else None


def _profile_variable(payload: dict[str, Any]) -> dict[str, Any]:
    responses = payload.get("responses", [])
    units: set[int] = set()
    categories: set[str] = set()
    category_dimensions: set[str] = set()
    period_types: set[str] = set()
    years: set[int] = set()
    titles: list[str] = []
    subjects: set[str] = set()
    last_updates: set[str] = set()
    observed = 0
    expected = 0

    for response in responses:
        observed += len(response.get("datacontent", {}))
        vervar = response.get("vervar", [])
        turvar = response.get("turvar", [])
        tahun = response.get("tahun", [])
        turtahun = response.get("turtahun", [])
        expected += len(vervar) * max(1, len(turvar)) * len(tahun) * max(1, len(turtahun))
        for item in vervar:
            units.add(int(item["val"]))
        for item in turvar:
            categories.add(str(item["label"]))
        for item in tahun:
            year = _year(item["label"])
            if year is not None:
                years.add(year)
        for item in turtahun:
            period_types.add(str(item["label"]).strip())
        if response.get("var"):
            titles.append(str(response["var"][0].get("label", "")).strip())
        for item in response.get("subject", []):
            subjects.add(str(item["label"]))
        if response.get("last_update"):
            last_updates.add(str(response["last_update"]))

    levels = {_classify_vervar(value) for value in units}
    if levels == {"non_spatial"} or not levels:
        # The unit dimension carries a breakdown rather than a geography, so the
        # series itself is national and the breakdown is recorded as a category.
        geography_levels = ["national"] if units else []
        dimension = str(next((r.get("labelvervar", "") for r in responses if r.get("labelvervar")), ""))
        if len(units) > 1:
            category_dimensions.add(dimension.strip())
    else:
        geography_levels = [level for level in GEOGRAPHY_ORDER if level in levels]

    ordered_years = sorted(years)
    gaps = (
        [year for year in range(ordered_years[0], ordered_years[-1] + 1) if year not in years]
        if ordered_years
        else []
    )
    return {
        "units": units,
        "geography_levels": geography_levels,
        "category_labels": sorted(label for label in categories if label != "Tidak ada"),
        "category_dimensions": sorted(item for item in category_dimensions if item),
        "period_types": sorted(period_types),
        "years": ordered_years,
        "period_gaps": gaps,
        "observed_cells": observed,
        "expected_cells": expected,
        "title": titles[0] if titles else "",
        "subject_name": "; ".join(sorted(subjects)),
        "last_update": max(last_updates) if last_updates else "",
    }


def _variable_row(entry: dict[str, Any], profile: dict[str, Any]) -> dict[str, str]:
    counts = {level: 0 for level in GEOGRAPHY_ORDER}
    for value in profile["units"]:
        level = _classify_vervar(value)
        if level in counts:
            counts[level] += 1
    if not any(counts.values()) and profile["geography_levels"] == ["national"]:
        counts["national"] = 1
    years = profile["years"]
    expected = profile["expected_cells"]
    return {
        "webapi_domain_id": entry["domain"],
        "webapi_variable_id": entry["variable_id"],
        "title": profile["title"],
        "subject_name": profile["subject_name"],
        "vervar_dimension": "; ".join(profile["category_dimensions"]),
        "geography_levels": ";".join(profile["geography_levels"]),
        "national_units": str(counts["national"]),
        "province_units": str(counts["province"]),
        "regency_units": str(counts["regency"]),
        "category_dimensions": "; ".join(profile["category_labels"]),
        "category_count": str(len(profile["category_labels"])),
        "period_types": ";".join(profile["period_types"]),
        "period_start": str(years[0]) if years else "",
        "period_end": str(years[-1]) if years else "",
        "period_count": str(len(years)),
        "period_gaps": ";".join(str(year) for year in profile["period_gaps"]),
        "observed_cells": str(profile["observed_cells"]),
        "expected_cells": str(expected),
        "cell_density": f"{profile['observed_cells'] / expected:.4f}" if expected else "",
        "last_update": profile["last_update"],
        "producer": entry.get("producer", ""),
        "indicator_keys": ";".join(entry.get("indicator_keys", [])),
        "selection_statuses": ";".join(entry.get("selection_statuses", [])),
    }


def _read_producers(selection_path: Path) -> dict[tuple[str, str], str]:
    producers: dict[tuple[str, str], str] = {}
    if not selection_path.exists():
        return producers
    with selection_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            variable_id = row["webapi_variable_id"].strip()
            if variable_id:
                producers.setdefault((row["webapi_domain_id"], variable_id), row["producer"])
    return producers


def _derive_status(
    *,
    proposed_geographies: list[str],
    verified_geographies: list[str],
    evidence_sources: set[str],
) -> tuple[str, str, list[str]]:
    """Decide H1 status from confirmed free-source coverage."""
    flags: list[str] = []
    shortfall = [level for level in proposed_geographies if level not in verified_geographies]
    if shortfall and evidence_sources:
        flags.append("geography_shortfall")

    if not evidence_sources:
        return "unavailable", "no_exact_free_series_confirmed", flags
    if shortfall:
        return "partial", "geography_shortfall", flags
    return "verified", "free_source_confirmed_full_geography", flags


def _read_publications(path: Path) -> dict[str, list[dict[str, str]]]:
    publications: dict[str, list[dict[str, str]]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["selection_status"] in PUBLICATION_SELECTION_STATUSES:
                publications.setdefault(row["indicator_key"], []).append(row)
    return publications


def profile_free_webapi(
    *,
    manifest_path: Path,
    selection_path: Path,
    publication_selection_path: Path,
    indicator_dir: Path,
    variable_output: Path,
    indicator_output: Path,
    minimum_span: int,
) -> dict[str, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    producers = _read_producers(selection_path)
    publications = _read_publications(publication_selection_path)

    variable_rows: list[dict[str, str]] = []
    profiles: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in manifest["files"]:
        raw_path = Path(entry["raw_path"])
        if not raw_path.exists():
            raise FileNotFoundError(
                f"{raw_path} is missing; run `make h1-fetch-free-webapi` to rebuild it from {manifest_path}"
            )
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        profile = _profile_variable(payload)
        key = (entry["domain"], entry["variable_id"])
        profiles[key] = profile
        enriched = {**entry, "producer": producers.get(key, "")}
        variable_rows.append(_variable_row(enriched, profile))
    variable_rows.sort(key=lambda row: (row["webapi_domain_id"], int(row["webapi_variable_id"])))
    _write_csv(variable_output, VARIABLE_COLUMNS, variable_rows)

    by_indicator: dict[str, list[tuple[str, str]]] = {}
    for entry in manifest["files"]:
        for indicator_key in entry["indicator_keys"]:
            by_indicator.setdefault(indicator_key, []).append((entry["domain"], entry["variable_id"]))

    indicator_rows: list[dict[str, str]] = []
    for path in indicator_paths(indicator_dir):
        _, rows = read_csv(path)
        for row in rows:
            indicator_rows.append(
                _indicator_row(
                    row,
                    by_indicator.get(row["indicator_key"], []),
                    profiles,
                    producers,
                    publications.get(row["indicator_key"], []),
                    minimum_span,
                )
            )
    _write_csv(indicator_output, INDICATOR_COLUMNS, indicator_rows)

    statuses: dict[str, int] = {}
    for row in indicator_rows:
        statuses[row["derived_status"]] = statuses.get(row["derived_status"], 0) + 1
    return {
        "variable_count": len(variable_rows),
        "indicator_count": len(indicator_rows),
        "statuses": statuses,
    }


def _indicator_row(
    row: dict[str, str],
    keys: list[tuple[str, str]],
    profiles: dict[tuple[str, str], dict[str, Any]],
    producers: dict[tuple[str, str], str],
    publications: list[dict[str, str]],
    minimum_span: int,
) -> dict[str, str]:
    selected = [profiles[key] for key in keys if key in profiles]
    levels: set[str] = set()
    years: set[int] = set()
    gaps: set[int] = set()
    period_types: set[str] = set()
    updates: set[str] = set()
    observed = 0
    evidence_sources: set[str] = set()
    for profile in selected:
        levels.update(profile["geography_levels"])
        years.update(profile["years"])
        gaps.update(profile["period_gaps"])
        period_types.update(profile["period_types"])
        observed += profile["observed_cells"]
        if profile["observed_cells"]:
            evidence_sources.add("bps_webapi")
        if profile["last_update"]:
            updates.add(profile["last_update"])

    for publication in publications:
        levels.update(item for item in publication["verified_geographies"].split(";") if item)
        start = publication["period_start"].strip()
        end = publication["period_end"].strip()
        if start and end:
            years.update(range(int(start), int(end) + 1))
        evidence_sources.add(publication["source_id"])

    verified_geographies = [level for level in GEOGRAPHY_ORDER if level in levels]
    proposed_geographies = [item for item in row["proposed_geographies"].split(";") if item]
    status, reason, flags = _derive_status(
        proposed_geographies=proposed_geographies,
        verified_geographies=verified_geographies,
        evidence_sources=evidence_sources,
    )

    ordered_years = sorted(years)
    real_gaps = sorted(gap for gap in gaps if gap not in years)
    if ordered_years and (ordered_years[-1] - ordered_years[0] + 1) < minimum_span:
        flags.append("short_series")
    if real_gaps:
        flags.append("period_gap")
    if len(period_types) > 1 or any(item not in {"Tahun", "Tahunan"} for item in period_types):
        flags.append("subannual_periods")
    if len(keys) > 1:
        flags.append("multi_variable")
    proposed_sources = {item for item in row["proposed_sources"].split(";") if item}
    if selected and "bps_webapi" not in proposed_sources:
        flags.append("webapi_found_unproposed")
    # These mappings require a transformation before they become an indicator.
    derived_keys = {"sdg07_clean_cooking", "sdg15_forest_cover", "sdg15_conservation_area", "sdg15_land_cover_change"}
    if row["indicator_key"] in derived_keys and evidence_sources:
        flags.append("derivation_required")
        if status == "verified":
            status, reason = "partial", "derivation_required"

    publication_years = sorted({publication["source_id"].removeprefix("bps_tpb_") for publication in publications})
    publication_locators = [
        f"{publication['locator']} (p. {publication['page']})" for publication in publications
    ]

    return {
        "indicator_key": row["indicator_key"],
        "domain": row["domain"],
        "sdg_code": row["sdg_code"],
        "proposed_geographies": row["proposed_geographies"],
        "proposed_sources": row["proposed_sources"],
        "webapi_domain_id": sorted({key[0] for key in keys})[0] if keys else "",
        "webapi_variable_ids": ";".join(str(item) for item in sorted({int(key[1]) for key in keys})),
        "verified_geographies": ";".join(verified_geographies),
        "period_start": str(ordered_years[0]) if ordered_years else "",
        "period_end": str(ordered_years[-1]) if ordered_years else "",
        "period_gaps": ";".join(str(gap) for gap in real_gaps),
        "observed_cells": str(observed),
        "last_update": max(updates) if updates else "",
        "tpb_publication_year": ";".join(publication_years),
        "tpb_table_or_page": "; ".join(publication_locators),
        "derived_status": status,
        "status_reason": reason,
        "derived_risk_flags": ";".join(sorted(set(flags))),
        "producer": "; ".join(
            sorted(
                ({producers.get(key, "") for key in keys}
                 | {publication.get("producer", "") for publication in publications})
                - {""}
            )
        ),
    }


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def apply_coverage(
    *,
    indicator_coverage: Path,
    indicator_dir: Path,
) -> dict[str, int]:
    """Write the derived coverage back into the shared indicator inventory.

    The inventory keeps only the decision and the locator; the evidence behind
    each decision stays in the coverage report so the two can be diffed.
    """
    _, coverage_rows = read_csv(indicator_coverage)
    derived = {row["indicator_key"]: row for row in coverage_rows}

    changed = 0
    for path in indicator_paths(indicator_dir):
        fields, rows = read_csv(path)
        for row in rows:
            source = derived.get(row["indicator_key"])
            if source is None:
                continue
            updates = {
                "webapi_domain_id": source["webapi_domain_id"],
                "webapi_variable_id": source["webapi_variable_ids"],
                "verified_geographies": source["verified_geographies"],
                "period_start": source["period_start"],
                "period_end": source["period_end"],
                "verification_status": source["derived_status"],
                "tpb_publication_year": source["tpb_publication_year"],
                "tpb_table_or_page": source["tpb_table_or_page"],
                "risk_flags": _merge_flags(row["risk_flags"], source["derived_risk_flags"]),
            }
            if source["producer"]:
                updates["producer"] = source["producer"]
            if any(row[field] != value for field, value in updates.items()):
                changed += 1
            row.update(updates)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return {"updated_rows": changed, "indicator_count": len(derived)}


def _merge_flags(existing: str, derived: str) -> str:
    merged: list[str] = []
    for flag in [item for item in existing.split(";") if item] + [
        item for item in derived.split(";") if item
    ]:
        if flag not in merged:
            merged.append(flag)
    return ";".join(merged)
