from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kkciv_vintage.h1.compare import compare_files
from kkciv_vintage.h2.pipeline import OBSERVATION_COLUMNS

from .geography import DISPLAY_NAMES, geo_level, normalise_name
from .publication_tables import extract_pages, parse_page, read_column


CELL_KEY = (
    "indicator_key",
    "series_key",
    "observed_period",
    "geo_level",
    "geo_code",
    "unit",
)
COMPARISON_COLUMNS = [
    "domain",
    *CELL_KEY,
    "geo_name",
    "source_count",
    "value_count",
    "min_value",
    "max_value",
    "absolute_spread",
    "status",
    "observations_json",
]
DISCREPANCY_COLUMNS = [
    "domain",
    *CELL_KEY,
    "absolute_spread",
    "source_values_json",
    "candidate_classification",
    "classification_note",
]
SUMMARY_COLUMNS = [
    "domain",
    "observation_rows",
    "unique_cells",
    "compared_cells",
    "exact_matches",
    "value_mismatches",
    "single_source_cells",
    "national_cells",
    "province_cells",
]
CHART_SCOPE_COLUMNS = [
    "domain",
    "indicator_key",
    "webapi_province_cells",
    "publication_province_cells",
    "overlap_province_cells",
    "webapi_province_year_start",
    "webapi_province_year_end",
    "coverage_status",
    "coverage_note",
]
BASELINE_DISCREPANCY_COLUMNS = [
    "indicator_key",
    "series_key",
    "observed_period",
    "geo_level",
    "geo_code",
    "geo_name",
    "unit",
    "webapi_value",
    "publication_value",
    "absolute_spread",
    "classification",
    "classification_reason",
]
GRANULARITY_COLUMNS = [
    "source_id",
    "indicator_key",
    "series_key",
    "observed_period",
    "unit",
    "national_value",
    "province_count",
    "province_min",
    "province_max",
    "province_unweighted_mean",
    "gap_vs_unweighted_mean",
    "national_within_province_range",
]
INDICATOR_SUMMARY_COLUMNS = [
    "domain",
    "indicator_key",
    "alignment_status",
    "geo_level",
    "overlap_cells",
    "exact_matches",
    "value_mismatches",
    "missing_snapshots",
    "mismatch_rate",
    "max_absolute_spread",
]


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


def _record_key(
    geography_id: str,
    variable_id: str,
    category_id: str,
    period_id: str,
    derived_period_id: str,
) -> str:
    return f"{geography_id}{variable_id}{category_id}{period_id}{derived_period_id}"


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def expand_publication_series(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for line_number, series in enumerate(_read_csv(path), start=2):
        for item in series["values"].split("|"):
            year, value = item.split(":", 1)
            if _decimal(value) is None:
                raise ValueError(f"{path}:{line_number}: non-numeric publication value {value!r}")
            row = {
                "source_id": series["source_id"],
                "indicator_key": series["indicator_key"],
                "series_key": series["series_key"],
                "release_date": series["release_date"],
                "observed_period": year,
                "geo_level": series["geo_level"],
                "geo_code": series["geo_code"],
                "geo_name": series["geo_name"],
                "unit": series["unit"],
                "value": value,
                "producer": series["producer"],
                "methodology_version": series["methodology_version"],
                "source_record_id": (
                    f"page={series['publication_page']};figure={series['publication_figure']};"
                    f"series={series['series_key']};year={year}"
                ),
            }
            key = (row["source_id"], *(row[column] for column in CELL_KEY))
            if key in seen:
                raise ValueError(f"{path}:{line_number}: duplicate publication cell {key}")
            seen.add(key)
            rows.append(row)
    return sorted(rows, key=lambda row: (row["source_id"], *(row[key] for key in CELL_KEY)))


def extract_webapi_observations(
    *, manifest_path: Path, series_path: Path
) -> tuple[list[dict[str, str]], int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {str(item["variable_id"]): item for item in manifest["files"]}
    release_date = str(manifest["retrieved_at"])[:10]
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    skipped_non_numeric = 0

    for mapping in _read_csv(series_path):
        variable_id = mapping["webapi_variable_id"]
        entry = entries.get(variable_id)
        if entry is None:
            raise ValueError(f"variable {variable_id} is missing from {manifest_path}")
        raw_path = Path(entry["raw_path"])
        if not raw_path.exists():
            raise FileNotFoundError(f"{raw_path} is missing; run `make h3-fetch` first")
        if _sha256(raw_path) != entry["sha256"]:
            raise ValueError(f"checksum mismatch for {raw_path}")
        payload = json.loads(raw_path.read_text(encoding="utf-8"))

        for response in payload.get("responses", []):
            variables = response.get("var", [])
            if not variables:
                continue
            variable = variables[0]
            categories = {
                str(item["val"]): item for item in response.get("turvar", [])
            }
            if mapping["webapi_category_id"] not in categories:
                continue
            derived = {
                str(item["val"]): item for item in response.get("turtahun", [])
            }
            if mapping["webapi_derived_period_id"] not in derived:
                continue
            geographies = response.get("vervar", [])
            if mapping["geography_mode"] == "fixed":
                geographies = [
                    item
                    for item in geographies
                    if str(item["val"]) == mapping["webapi_geography_id"]
                ]
            elif mapping["geography_mode"] != "province_and_national":
                raise ValueError(f"unknown geography mode {mapping['geography_mode']!r}")

            for geography in geographies:
                geography_id = str(geography["val"])
                if mapping["geography_mode"] == "province_and_national":
                    if geography_id == "9999":
                        geo_level, geo_code, geo_name = "national", "9999", "Indonesia"
                    elif len(geography_id) == 4 and geography_id.endswith("00"):
                        geo_level = "province"
                        geo_code = geography_id
                        geo_name = str(geography["label"]).title()
                    else:
                        continue
                else:
                    geo_level = mapping["output_geo_level"]
                    geo_code = mapping["output_geo_code"]
                    geo_name = mapping["output_geo_name"]

                for period in response.get("tahun", []):
                    source_key = _record_key(
                        geography_id,
                        str(variable["val"]),
                        mapping["webapi_category_id"],
                        str(period["val"]),
                        mapping["webapi_derived_period_id"],
                    )
                    if source_key not in response.get("datacontent", {}):
                        continue
                    raw_value = response["datacontent"][source_key]
                    if _decimal(raw_value) is None:
                        skipped_non_numeric += 1
                        continue
                    updated = str(response.get("last_update", "")).split(" ", 1)[0]
                    row = {
                        "source_id": "bps_webapi",
                        "indicator_key": mapping["indicator_key"],
                        "series_key": mapping["series_key"],
                        "release_date": release_date,
                        "observed_period": str(period["label"]),
                        "geo_level": geo_level,
                        "geo_code": geo_code,
                        "geo_name": geo_name,
                        "unit": mapping["unit"],
                        "value": str(raw_value),
                        "producer": mapping["producer"],
                        "methodology_version": (
                            f"webapi-var-{variable_id}-updated-{updated}"
                        ),
                        "source_record_id": (
                            f"domain={payload['request']['domain']};var={variable_id};"
                            f"vervar={geography_id};turvar={mapping['webapi_category_id']};"
                            f"th={period['val']};turth={mapping['webapi_derived_period_id']}"
                        ),
                    }
                    key = (row["source_id"], *(row[column] for column in CELL_KEY))
                    if key in seen:
                        raise ValueError(f"duplicate WebAPI cell {key}")
                    seen.add(key)
                    rows.append(row)

    rows.sort(key=lambda row: (row["source_id"], *(row[key] for key in CELL_KEY)))
    return rows, skipped_non_numeric


def compare_sparse_sources(
    observations: list[dict[str, str]], domain_by_indicator: dict[str, str]
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[tuple(row[column] for column in CELL_KEY)].append(row)

    output: list[dict[str, str]] = []
    for key, group in sorted(grouped.items()):
        sources = {row["source_id"] for row in group}
        if len(sources) != len(group):
            raise ValueError(f"duplicate source within comparison cell {key}")
        values = [Decimal(row["value"]) for row in group]
        low, high = min(values), max(values)
        if len(sources) == 1:
            status = "single_source"
        elif len(set(values)) == 1:
            status = "exact_match"
        else:
            status = "value_mismatch"
        output.append(
            {
                "domain": domain_by_indicator[key[0]],
                **dict(zip(CELL_KEY, key)),
                "geo_name": group[0]["geo_name"],
                "source_count": str(len(sources)),
                "value_count": str(len(set(values))),
                "min_value": str(low),
                "max_value": str(high),
                "absolute_spread": str(high - low),
                "status": status,
                "observations_json": json.dumps(
                    sorted(group, key=lambda row: row["source_id"]),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return output


def _discrepancies(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        if row["status"] != "value_mismatch":
            continue
        observations = json.loads(row["observations_json"])
        source_values = {item["source_id"]: item["value"] for item in observations}
        if row["indicator_key"] == "sdg15_forest_cover":
            candidate = "methodology_or_denominator_change_candidate"
            note = "The publication title and displayed denominator changed; H4 must test the rule"
        elif row["indicator_key"] == "sdg07_energy_intensity":
            candidate = "methodology_or_unit_change_candidate"
            note = (
                "The 2018 gap is too large for rounding or an ordinary small revision; "
                "H4 must test the unit, denominator, and methodology"
            )
        else:
            candidate = "release_revision_candidate"
            note = "The same indicator cell differs between dated official releases; H4 must test the rule"
        output.append(
            {
                **{column: row[column] for column in ("domain", *CELL_KEY)},
                "absolute_spread": row["absolute_spread"],
                "source_values_json": json.dumps(
                    source_values, ensure_ascii=False, sort_keys=True
                ),
                "candidate_classification": candidate,
                "classification_note": note,
            }
        )
    return output


def _summary(
    observations: list[dict[str, str]], comparisons: list[dict[str, str]]
) -> list[dict[str, str]]:
    observation_counts = Counter()
    for row in observations:
        observation_counts[row["indicator_key"]] += 1
    domains = sorted({row["domain"] for row in comparisons})
    output: list[dict[str, str]] = []
    for domain in domains:
        rows = [row for row in comparisons if row["domain"] == domain]
        status = Counter(row["status"] for row in rows)
        indicator_keys = {row["indicator_key"] for row in rows}
        output.append(
            {
                "domain": domain,
                "observation_rows": str(
                    sum(observation_counts[key] for key in indicator_keys)
                ),
                "unique_cells": str(len(rows)),
                "compared_cells": str(status["exact_match"] + status["value_mismatch"]),
                "exact_matches": str(status["exact_match"]),
                "value_mismatches": str(status["value_mismatch"]),
                "single_source_cells": str(status["single_source"]),
                "national_cells": str(sum(row["geo_level"] == "national" for row in rows)),
                "province_cells": str(sum(row["geo_level"] == "province" for row in rows)),
            }
        )
    return output


def _release_chart_scope(
    observations: list[dict[str, str]], domain_by_indicator: dict[str, str]
) -> list[dict[str, str]]:
    web_cells: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    publication_cells: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    years: dict[str, set[str]] = defaultdict(set)
    for row in observations:
        if row["geo_level"] != "province":
            continue
        key = tuple(row[column] for column in CELL_KEY)
        if row["source_id"] == "bps_webapi":
            web_cells[row["indicator_key"]].add(key)
            years[row["indicator_key"]].add(row["observed_period"])
        else:
            publication_cells[row["indicator_key"]].add(key)

    output: list[dict[str, str]] = []
    for indicator_key, domain in sorted(
        domain_by_indicator.items(), key=lambda item: (item[1], item[0])
    ):
        web = web_cells[indicator_key]
        publication = publication_cells[indicator_key]
        overlap = web & publication
        if web and not publication:
            status = "webapi_province_outside_chart_supplement"
            note = (
                "The configured TPB 2024/2025 chart supplement is national; "
                "the full TPB 2024 appendix comparison is in h3-cell-comparison.csv"
            )
        elif not web and not publication:
            status = "national_chart_only"
            note = (
                "This release supplement configures national chart cells only; consult the "
                "baseline appendix comparison and its explicit alignment decisions"
            )
        elif publication and not web:
            status = "publication_province_only"
            note = "The configured chart series has province cells without aligned WebAPI cells"
        else:
            status = "comparable" if overlap else "non_overlapping"
            note = "Province cells are present in both sources" if overlap else "Province keys do not overlap"
        available_years = sorted(years[indicator_key])
        output.append(
            {
                "domain": domain,
                "indicator_key": indicator_key,
                "webapi_province_cells": str(len(web)),
                "publication_province_cells": str(len(publication)),
                "overlap_province_cells": str(len(overlap)),
                "webapi_province_year_start": available_years[0] if available_years else "",
                "webapi_province_year_end": available_years[-1] if available_years else "",
                "coverage_status": status,
                "coverage_note": note,
            }
        )
    return output


def run_h3_release_supplement(
    *,
    webapi_manifest: Path,
    webapi_series: Path,
    publication_series: Path,
    publication_manifest: Path,
    exclusions: Path,
    webapi_output: Path,
    publication_output: Path,
    normalized_output: Path,
    comparison_output: Path,
    discrepancy_output: Path,
    summary_output: Path,
    chart_scope_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    mappings = _read_csv(webapi_series)
    publication_specs = _read_csv(publication_series)
    domain_by_indicator = {
        row["indicator_key"]: row["domain"] for row in mappings
    }
    domain_by_indicator["sdg15_forest_cover"] = "ecology"

    publication_manifest_data = json.loads(
        publication_manifest.read_text(encoding="utf-8")
    )
    publication_sources = {row["source_id"] for row in publication_specs}
    publication_inputs: list[dict[str, str]] = []
    for entry in publication_manifest_data["files"]:
        if entry["source_id"] not in publication_sources:
            continue
        pdf = Path(entry["raw_path"])
        if not pdf.exists():
            raise FileNotFoundError(
                f"{pdf} is missing; run `make h1-fetch-free-publications` first"
            )
        if _sha256(pdf) != entry["sha256"]:
            raise ValueError(f"checksum mismatch for {pdf}")
        publication_inputs.append(
            {"path": str(pdf), "sha256": entry["sha256"], "source_id": entry["source_id"]}
        )
    if {item["source_id"] for item in publication_inputs} != publication_sources:
        raise ValueError("publication manifest does not contain every configured publication")

    webapi_rows, skipped_non_numeric = extract_webapi_observations(
        manifest_path=webapi_manifest, series_path=webapi_series
    )
    publication_rows = expand_publication_series(publication_series)
    observations = sorted(
        webapi_rows + publication_rows,
        key=lambda row: (row["source_id"], *(row[key] for key in CELL_KEY)),
    )
    comparisons = compare_sparse_sources(observations, domain_by_indicator)
    discrepancies = _discrepancies(comparisons)
    summary = _summary(observations, comparisons)
    chart_scope = _release_chart_scope(observations, domain_by_indicator)

    output_specs = [
        (webapi_output, OBSERVATION_COLUMNS, webapi_rows),
        (publication_output, OBSERVATION_COLUMNS, publication_rows),
        (normalized_output, OBSERVATION_COLUMNS, observations),
        (comparison_output, COMPARISON_COLUMNS, comparisons),
        (discrepancy_output, DISCREPANCY_COLUMNS, discrepancies),
        (summary_output, SUMMARY_COLUMNS, summary),
        (chart_scope_output, CHART_SCOPE_COLUMNS, chart_scope),
    ]
    outputs = []
    for path, columns, rows in output_specs:
        outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    mismatch_domains = sorted({row["domain"] for row in discrepancies})
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": "H3",
        "policy": {
            "cost_class": "free",
            "geographies": ["national", "province"],
            "comparison_semantics": "compare when at least two configured source releases share a cell",
            "excluded_sources": ["bps_dna", "bps_sirusa", "silastik_pst", "paid_digital_maps"],
            "classification_status": "candidate_only_until_H4",
        },
        "gate_g1": {
            "criterion_1_required_mismatch_domains": 3,
            "criterion_1_observed_domains": mismatch_domains,
            "criterion_1_passed": len(mismatch_domains) >= 3,
            "overall_gate_status": "pending_H4_classification_and_H5_revision_trace",
        },
        "skipped_non_numeric_webapi_cells": skipped_non_numeric,
        "inputs": [
            {"path": str(webapi_manifest), "sha256": _sha256(webapi_manifest)},
            {"path": str(webapi_series), "sha256": _sha256(webapi_series)},
            {"path": str(publication_series), "sha256": _sha256(publication_series)},
            {"path": str(publication_manifest), "sha256": _sha256(publication_manifest)},
            {"path": str(exclusions), "sha256": _sha256(exclusions)},
            *publication_inputs,
        ],
        "outputs": outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "webapi_rows": len(webapi_rows),
        "publication_rows": len(publication_rows),
        "comparison_rows": len(comparisons),
        "discrepancy_rows": len(discrepancies),
        "mismatch_domains": mismatch_domains,
        "skipped_non_numeric": skipped_non_numeric,
    }


def _publication_code_map(webapi_manifest: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in webapi_manifest["files"]:
        payload = json.loads(Path(entry["raw_path"]).read_text(encoding="utf-8"))
        for response in payload.get("responses", []):
            for geography in response.get("vervar", []):
                code = str(geography["val"])
                if code == "9999" or (len(code) == 4 and code.endswith("00")):
                    mapping[normalise_name(str(geography["label"]))] = code
    return mapping


def extract_province_publication_observations(
    *,
    pdf_path: Path,
    columns_path: Path,
    webapi_manifest: dict[str, Any],
    release_date: str,
    publication_id: str,
) -> list[dict[str, str]]:
    pages = extract_pages(pdf_path)
    code_by_name = _publication_code_map(webapi_manifest)
    rows: list[dict[str, str]] = []
    parsed_pages: dict[int, dict[str, Any]] = {}
    for mapping in _read_csv(columns_path):
        page_number = int(mapping["publication_page"])
        if page_number not in parsed_pages:
            parsed = parse_page(pages[page_number - 1])
            if parsed is None or parsed["incomplete_rows"]:
                raise ValueError(
                    f"publication page {page_number} is incomplete: "
                    f"{None if parsed is None else parsed['incomplete_rows']}"
                )
            parsed_pages[page_number] = parsed
        cells = read_column(parsed_pages[page_number], mapping["publication_column"])
        for name_key, cell in cells.items():
            if not cell["value"]:
                continue
            code = code_by_name.get(name_key)
            if code is None:
                raise ValueError(f"no WebAPI geography code for publication name {name_key}")
            methodology = "tpb-2024-appendix"
            if cell["note"]:
                methodology += f";{cell['note']}"
            rows.append(
                {
                    "source_id": "bps_tpb_2024",
                    "indicator_key": mapping["indicator_key"],
                    "series_key": mapping["series_key"],
                    "release_date": release_date,
                    "observed_period": mapping["observed_period"],
                    "geo_level": geo_level(code),
                    "geo_code": code,
                    "geo_name": DISPLAY_NAMES[name_key],
                    "unit": mapping["unit"],
                    "value": cell["value"],
                    "producer": mapping["producer"],
                    "methodology_version": methodology,
                    "source_record_id": (
                        f"pub={publication_id};page={page_number};"
                        f"column={mapping['publication_column']};year={mapping['observed_period']}"
                    ),
                }
            )
    return sorted(rows, key=lambda row: tuple(row[key] for key in CELL_KEY))


def extract_province_webapi_observations(
    *,
    manifest: dict[str, Any],
    indicators_path: Path,
    columns_path: Path,
    publication_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    indicators = {
        row["indicator_key"]: row
        for row in _read_csv(indicators_path)
        if row["alignment_status"] == "comparable"
    }
    columns = _read_csv(columns_path)
    entry_by_variable = {
        str(entry["variable_id"]): entry for entry in manifest["files"]
    }
    release_date = str(manifest["retrieved_at"])[:10]
    expected = {
        tuple(row[key] for key in CELL_KEY): row for row in publication_rows
    }
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for mapping in columns:
        if mapping["indicator_key"] not in indicators:
            continue
        indicator = indicators[mapping["indicator_key"]]
        variable_id = indicator["webapi_variable_id"]
        entry = entry_by_variable[variable_id]
        raw_path = Path(entry["raw_path"])
        if _sha256(raw_path) != entry["sha256"]:
            raise ValueError(f"checksum mismatch for {raw_path}")
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        for response in payload.get("responses", []):
            if not response.get("var"):
                continue
            variable = response["var"][0]
            categories = {
                str(item["val"]): item for item in response.get("turvar", [])
            }
            periods = [
                item
                for item in response.get("tahun", [])
                if str(item["label"]) == mapping["observed_period"]
            ]
            if mapping["webapi_category_id"] not in categories or not periods:
                continue
            derived_ids = {
                str(item["val"]) for item in response.get("turtahun", [])
            }
            period_type = indicator["webapi_period_type_id"]
            if period_type not in derived_ids:
                continue
            for geography in response.get("vervar", []):
                code = str(geography["val"])
                level = geo_level(code)
                if level not in {"national", "province"}:
                    continue
                period = periods[0]
                source_key = _record_key(
                    code,
                    str(variable["val"]),
                    mapping["webapi_category_id"],
                    str(period["val"]),
                    period_type,
                )
                if source_key not in response.get("datacontent", {}):
                    continue
                value = response["datacontent"][source_key]
                if _decimal(value) is None:
                    continue
                row_key = (
                    mapping["indicator_key"],
                    mapping["series_key"],
                    mapping["observed_period"],
                    level,
                    code,
                    mapping["unit"],
                )
                if row_key not in expected or row_key in seen:
                    continue
                seen.add(row_key)
                updated = str(response.get("last_update", "")).split(" ", 1)[0]
                rows.append(
                    {
                        "source_id": "bps_webapi",
                        "indicator_key": mapping["indicator_key"],
                        "series_key": mapping["series_key"],
                        "release_date": release_date,
                        "observed_period": mapping["observed_period"],
                        "geo_level": level,
                        "geo_code": code,
                        "geo_name": (
                            "Indonesia"
                            if level == "national"
                            else str(geography["label"]).title()
                        ),
                        "unit": mapping["unit"],
                        "value": str(value),
                        "producer": mapping["producer"],
                        "methodology_version": (
                            f"webapi-var-{variable_id}-updated-{updated}"
                        ),
                        "source_record_id": (
                            f"domain={payload['request']['domain']};var={variable_id};"
                            f"vervar={code};turvar={mapping['webapi_category_id']};"
                            f"th={period['val']};turth={period_type}"
                        ),
                    }
                )
    if set(expected) != seen:
        missing = sorted(set(expected) - seen)
        raise ValueError(f"WebAPI lacks {len(missing)} publication cells; first={missing[:1]}")
    return sorted(rows, key=lambda row: tuple(row[key] for key in CELL_KEY))


def classify(
    comparison_rows: list[dict[str, str]], publication_release_date: str
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for compared in comparison_rows:
        if compared["status"] != "value_mismatch":
            continue
        observations = json.loads(compared["observations_json"])
        by_source = {item["source_id"]: item for item in observations}
        web = by_source["bps_webapi"]
        publication = by_source["bps_tpb_2024"]
        publication_value = publication["value"]
        decimals = len(publication_value.split(".", 1)[1]) if "." in publication_value else 0
        unit_in_last_place = Decimal(1).scaleb(-decimals)
        spread = Decimal(compared["absolute_spread"])
        if spread <= unit_in_last_place:
            classification = "last_digit_difference"
            reason = (
                "The two channels differ by at most one unit in the last published "
                f"decimal place ({unit_in_last_place}), which rounding alone can produce"
            )
        else:
            updated = web["methodology_version"].rsplit("-updated-", 1)[-1]
            if updated > publication_release_date:
                classification = "candidate_revision"
                reason = (
                    f"WebAPI table was updated on {updated}, after the "
                    f"{publication_release_date} publication"
                )
            else:
                classification = "unclassified_difference"
                reason = "The difference exceeds the published precision and has no later update marker"
        output.append(
            {
                **{key: compared[key] for key in CELL_KEY},
                "geo_name": compared["geo_name"],
                "webapi_value": web["value"],
                "publication_value": publication["value"],
                "absolute_spread": compared["absolute_spread"],
                "classification": classification,
                "classification_reason": reason,
            }
        )
    return output


def granularity_report(observations: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        key = (
            row["source_id"],
            row["indicator_key"],
            row["series_key"],
            row["observed_period"],
            row["unit"],
        )
        grouped[key].append(row)
    output: list[dict[str, str]] = []
    for key, rows in sorted(grouped.items()):
        national = [Decimal(row["value"]) for row in rows if row["geo_level"] == "national"]
        provinces = [Decimal(row["value"]) for row in rows if row["geo_level"] == "province"]
        if len(national) != 1 or not provinces:
            continue
        value = national[0]
        mean = sum(provinces) / len(provinces)
        output.append(
            {
                "source_id": key[0],
                "indicator_key": key[1],
                "series_key": key[2],
                "observed_period": key[3],
                "unit": key[4],
                "national_value": str(value),
                "province_count": str(len(provinces)),
                "province_min": str(min(provinces)),
                "province_max": str(max(provinces)),
                "province_unweighted_mean": f"{mean:.4f}",
                "gap_vs_unweighted_mean": f"{value - mean:.4f}",
                "national_within_province_range": (
                    "yes" if min(provinces) <= value <= max(provinces) else "no"
                ),
            }
        )
    return output


def _indicator_summary(
    comparisons: list[dict[str, str]], indicators_path: Path
) -> list[dict[str, str]]:
    configured = [
        row
        for row in _read_csv(indicators_path)
        if row["alignment_status"] == "comparable"
    ]
    indicators = {row["indicator_key"]: row for row in configured}
    indicator_rank = {row["indicator_key"]: index for index, row in enumerate(configured)}
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in comparisons:
        grouped[(row["indicator_key"], row["geo_level"])].append(row)
    output: list[dict[str, str]] = []
    level_rank = {"national": 0, "province": 1}
    for (indicator_key, level), rows in sorted(
        grouped.items(), key=lambda item: (indicator_rank[item[0][0]], level_rank[item[0][1]])
    ):
        counts = Counter(row["status"] for row in rows)
        overlap = counts["exact_match"] + counts["value_mismatch"]
        spreads = [Decimal(row["absolute_spread"]) for row in rows]
        output.append(
            {
                "domain": indicators[indicator_key]["domain"],
                "indicator_key": indicator_key,
                "alignment_status": indicators[indicator_key]["alignment_status"],
                "geo_level": level,
                "overlap_cells": str(overlap),
                "exact_matches": str(counts["exact_match"]),
                "value_mismatches": str(counts["value_mismatch"]),
                "missing_snapshots": str(counts["missing_snapshot"]),
                "mismatch_rate": f"{counts['value_mismatch'] / overlap:.4f}" if overlap else "",
                "max_absolute_spread": str(max(spreads)) if spreads else "",
            }
        )
    return output


def run_h3(
    *,
    indicators_path: Path,
    columns_path: Path,
    webapi_manifest_path: Path,
    publication_manifest_path: Path,
    webapi_output: Path,
    publication_output: Path,
    comparison_output: Path,
    discrepancy_output: Path,
    granularity_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    webapi_manifest = json.loads(webapi_manifest_path.read_text(encoding="utf-8"))
    publication_manifest = json.loads(
        publication_manifest_path.read_text(encoding="utf-8")
    )
    publication_entry = next(
        item for item in publication_manifest["files"] if item["source_id"] == "bps_tpb_2024"
    )
    pdf = Path(publication_entry["raw_path"])
    if _sha256(pdf) != publication_entry["sha256"]:
        raise ValueError(f"checksum mismatch for {pdf}")

    publication_rows = extract_province_publication_observations(
        pdf_path=pdf,
        columns_path=columns_path,
        webapi_manifest=webapi_manifest,
        release_date=publication_entry["release_date"],
        publication_id=publication_entry["publication_id"],
    )
    comparable = {
        row["indicator_key"]
        for row in _read_csv(indicators_path)
        if row["alignment_status"] == "comparable"
    }
    publication_rows = [
        row for row in publication_rows if row["indicator_key"] in comparable
    ]
    webapi_rows = extract_province_webapi_observations(
        manifest=webapi_manifest,
        indicators_path=indicators_path,
        columns_path=columns_path,
        publication_rows=publication_rows,
    )
    webapi_sha = _write_csv(webapi_output, OBSERVATION_COLUMNS, webapi_rows)
    publication_sha = _write_csv(publication_output, OBSERVATION_COLUMNS, publication_rows)
    comparisons = compare_files([webapi_output, publication_output], comparison_output)
    discrepancies = classify(comparisons, publication_entry["release_date"])
    discrepancy_sha = _write_csv(
        discrepancy_output, BASELINE_DISCREPANCY_COLUMNS, discrepancies
    )
    granularity = granularity_report(webapi_rows + publication_rows)
    granularity_sha = _write_csv(
        granularity_output, GRANULARITY_COLUMNS, granularity
    )
    summary = _indicator_summary(comparisons, indicators_path)
    summary_sha = _write_csv(summary_output, INDICATOR_SUMMARY_COLUMNS, summary)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": [
            {"path": str(indicators_path), "sha256": _sha256(indicators_path)},
            {"path": str(columns_path), "sha256": _sha256(columns_path)},
            {"path": str(webapi_manifest_path), "sha256": _sha256(webapi_manifest_path)},
            {"path": str(publication_manifest_path), "sha256": _sha256(publication_manifest_path)},
            {"path": str(pdf), "sha256": publication_entry["sha256"], "source_id": "bps_tpb_2024"},
        ],
        "outputs": [
            {"path": str(webapi_output), "rows": len(webapi_rows), "sha256": webapi_sha},
            {"path": str(publication_output), "rows": len(publication_rows), "sha256": publication_sha},
            {"path": str(comparison_output), "rows": len(comparisons), "sha256": _sha256(comparison_output)},
            {"path": str(discrepancy_output), "rows": len(discrepancies), "sha256": discrepancy_sha},
            {"path": str(granularity_output), "rows": len(granularity), "sha256": granularity_sha},
            {"path": str(summary_output), "rows": len(summary), "sha256": summary_sha},
        ],
        "policy": {
            "cost_class": "free",
            "geographies": ["national", "province"],
            "publication_release": publication_entry["release_date"],
            "webapi_snapshot": str(webapi_manifest["retrieved_at"])[:10],
        },
        "stage": "H3",
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "webapi_rows": len(webapi_rows),
        "publication_rows": len(publication_rows),
        "comparison_rows": len(comparisons),
        "discrepancy_rows": len(discrepancies),
        "granularity_rows": len(granularity),
    }
