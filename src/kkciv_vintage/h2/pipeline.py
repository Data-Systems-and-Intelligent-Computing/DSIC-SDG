from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from kkciv_vintage.h1.compare import compare_files


OBSERVATION_COLUMNS = [
    "source_id",
    "indicator_key",
    "series_key",
    "release_date",
    "observed_period",
    "geo_level",
    "geo_code",
    "geo_name",
    "unit",
    "value",
    "producer",
    "methodology_version",
    "source_record_id",
]
SUMMARY_COLUMNS = [
    "domain",
    "indicator_key",
    "alignment_status",
    "comparison_result",
    "publication_cells",
    "webapi_cells",
    "overlap_cells",
    "exact_matches",
    "value_mismatches",
    "missing_snapshots",
    "mismatch_rate_overlapping",
    "max_absolute_spread",
    "alignment_reason",
]
DISCREPANCY_COLUMNS = [
    "indicator_key",
    "series_key",
    "observed_period",
    "geo_level",
    "geo_code",
    "unit",
    "webapi_value",
    "publication_value",
    "absolute_spread",
    "classification",
    "classification_note",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return _sha256(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _record_key(
    *,
    geography_id: str,
    variable_id: str,
    category_id: str,
    period_id: str,
    derived_period_id: str,
) -> str:
    return f"{geography_id}{variable_id}{category_id}{period_id}{derived_period_id}"


def extract_webapi_series(
    *,
    payload: dict[str, Any],
    indicator_key: str,
    series_key: str,
    category_id: str,
    unit: str,
    producer: str,
    release_date: str,
    selected_years: set[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for response in payload.get("responses", []):
        variable = response["var"][0]
        variable_id = str(variable["val"])
        national = next(
            (item for item in response.get("vervar", []) if str(item["val"]) == "9999"),
            None,
        )
        category = next(
            (item for item in response.get("turvar", []) if str(item["val"]) == category_id),
            None,
        )
        if national is None or category is None:
            continue
        for period in response.get("tahun", []):
            year = str(period["label"])
            if year not in selected_years:
                continue
            for derived_period in response.get("turtahun", []):
                if str(derived_period["label"]).strip() not in {"Tahun", "Tahunan"}:
                    continue
                source_key = _record_key(
                    geography_id=str(national["val"]),
                    variable_id=variable_id,
                    category_id=category_id,
                    period_id=str(period["val"]),
                    derived_period_id=str(derived_period["val"]),
                )
                if source_key not in response.get("datacontent", {}):
                    continue
                cell = (series_key, year)
                if cell in seen:
                    raise ValueError(f"duplicate WebAPI cell for {indicator_key}/{series_key}/{year}")
                seen.add(cell)
                last_update = str(response.get("last_update", "")).split(" ", 1)[0]
                rows.append(
                    {
                        "source_id": "bps_webapi",
                        "indicator_key": indicator_key,
                        "series_key": series_key,
                        "release_date": release_date,
                        "observed_period": year,
                        "geo_level": "national",
                        "geo_code": "9999",
                        "geo_name": str(national["label"]).title(),
                        "unit": unit,
                        "value": str(response["datacontent"][source_key]),
                        "producer": producer,
                        "methodology_version": f"webapi-var-{variable_id}-updated-{last_update}",
                        "source_record_id": (
                            f"domain={payload['request']['domain']};var={variable_id};"
                            f"vervar=9999;turvar={category_id};th={period['val']};"
                            f"turth={derived_period['val']}"
                        ),
                    }
                )
    return sorted(rows, key=lambda row: (row["indicator_key"], row["series_key"], row["observed_period"]))


def _summarize(
    *,
    indicators: list[dict[str, str]],
    webapi_rows: list[dict[str, str]],
    publication_rows: list[dict[str, str]],
    comparison_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    web_counts = Counter(row["indicator_key"] for row in webapi_rows)
    publication_counts = Counter(row["indicator_key"] for row in publication_rows)
    compared: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in comparison_rows:
        compared[row["indicator_key"]].append(row)

    summary: list[dict[str, str]] = []
    for indicator in indicators:
        key = indicator["indicator_key"]
        rows = compared[key]
        counts = Counter(row["status"] for row in rows)
        overlap = counts["exact_match"] + counts["value_mismatch"]
        mismatches = counts["value_mismatch"]
        spreads = [Decimal(row["absolute_spread"]) for row in rows if row["absolute_spread"]]
        if indicator["alignment_status"] != "comparable":
            result = indicator["alignment_status"]
        elif mismatches:
            result = "value_mismatch_detected"
        elif counts["missing_snapshot"]:
            result = "coverage_gap_only"
        else:
            result = "exact_match"
        summary.append(
            {
                "domain": indicator["domain"],
                "indicator_key": key,
                "alignment_status": indicator["alignment_status"],
                "comparison_result": result,
                "publication_cells": str(publication_counts[key]),
                "webapi_cells": str(web_counts[key]),
                "overlap_cells": str(overlap),
                "exact_matches": str(counts["exact_match"]),
                "value_mismatches": str(mismatches),
                "missing_snapshots": str(counts["missing_snapshot"]),
                "mismatch_rate_overlapping": (
                    f"{mismatches / overlap:.4f}" if overlap else ""
                ),
                "max_absolute_spread": str(max(spreads)) if spreads else "",
                "alignment_reason": indicator["alignment_reason"],
            }
        )
    return summary


def _discrepancies(comparison_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for compared in comparison_rows:
        if compared["status"] == "exact_match":
            continue
        observations = json.loads(compared["observations_json"])
        values = {item["source_id"]: item["value"] for item in observations}
        if compared["status"] == "value_mismatch":
            classification = "unclassified_difference"
            note = "H3 must distinguish release revision from methodology change"
        else:
            classification = "coverage_gap"
            note = "The publication contains a period absent from the selected WebAPI variable"
        rows.append(
            {
                "indicator_key": compared["indicator_key"],
                "series_key": compared["series_key"],
                "observed_period": compared["observed_period"],
                "geo_level": compared["geo_level"],
                "geo_code": compared["geo_code"],
                "unit": compared["unit"],
                "webapi_value": values.get("bps_webapi", ""),
                "publication_value": values.get("bps_tpb_2024", ""),
                "absolute_spread": compared["absolute_spread"],
                "classification": classification,
                "classification_note": note,
            }
        )
    return rows


def run_h2_pilot(
    *,
    indicator_selection: Path,
    series_selection: Path,
    publication_reference: Path,
    h1_webapi_manifest: Path,
    h1_publication_manifest: Path,
    webapi_output: Path,
    publication_output: Path,
    normalized_output: Path,
    comparison_output: Path,
    discrepancy_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    indicators = _read_csv(indicator_selection)
    indicator_by_key = {row["indicator_key"]: row for row in indicators}
    eligible = {
        row["indicator_key"] for row in indicators if row["alignment_status"] == "comparable"
    }
    series = _read_csv(series_selection)
    publication_all = _read_csv(publication_reference)
    publication_rows = [
        {column: row[column] for column in OBSERVATION_COLUMNS}
        for row in publication_all
        if row["indicator_key"] in eligible
    ]
    publication_rows.sort(
        key=lambda row: (row["indicator_key"], row["series_key"], row["observed_period"])
    )

    publication_manifest = json.loads(
        h1_publication_manifest.read_text(encoding="utf-8")
    )
    publication_entry = next(
        item
        for item in publication_manifest["files"]
        if item["source_id"] == "bps_tpb_2024"
    )
    publication_pdf = Path(publication_entry["raw_path"])
    if not publication_pdf.exists():
        raise FileNotFoundError(
            f"{publication_pdf} is missing; run `make h1-fetch-free-publications` first"
        )
    if _sha256(publication_pdf) != publication_entry["sha256"]:
        raise ValueError(f"checksum mismatch for {publication_pdf}")

    h1_manifest = json.loads(h1_webapi_manifest.read_text(encoding="utf-8"))
    manifest_entries = {
        (entry["domain"], entry["variable_id"]): entry for entry in h1_manifest["files"]
    }
    release_date = str(h1_manifest["retrieved_at"])[:10]
    reference_years: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in publication_rows:
        reference_years[(row["indicator_key"], row["series_key"])].add(row["observed_period"])

    webapi_rows: list[dict[str, str]] = []
    for mapping in series:
        indicator = indicator_by_key[mapping["indicator_key"]]
        manifest_entry = manifest_entries[
            (indicator["webapi_domain_id"], indicator["webapi_variable_id"])
        ]
        raw_path = Path(manifest_entry["raw_path"])
        if not raw_path.exists():
            raise FileNotFoundError(
                f"{raw_path} is missing; run `make h1-fetch-free-webapi` first"
            )
        if _sha256(raw_path) != manifest_entry["sha256"]:
            raise ValueError(f"checksum mismatch for {raw_path}")
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        webapi_rows.extend(
            extract_webapi_series(
                payload=payload,
                indicator_key=mapping["indicator_key"],
                series_key=mapping["series_key"],
                category_id=mapping["webapi_category_id"],
                unit=mapping["unit"],
                producer=mapping["producer"],
                release_date=release_date,
                selected_years=reference_years[
                    (mapping["indicator_key"], mapping["series_key"])
                ],
            )
        )
    webapi_rows.sort(
        key=lambda row: (row["indicator_key"], row["series_key"], row["observed_period"])
    )

    webapi_sha = _write_csv(webapi_output, OBSERVATION_COLUMNS, webapi_rows)
    publication_sha = _write_csv(
        publication_output, OBSERVATION_COLUMNS, publication_rows
    )
    normalized_rows = sorted(
        webapi_rows + publication_rows,
        key=lambda row: (
            row["indicator_key"],
            row["series_key"],
            row["observed_period"],
            row["source_id"],
        ),
    )
    normalized_sha = _write_csv(
        normalized_output, OBSERVATION_COLUMNS, normalized_rows
    )
    comparison_rows = compare_files([webapi_output, publication_output], comparison_output)
    discrepancy_rows = _discrepancies(comparison_rows)
    discrepancy_sha = _write_csv(
        discrepancy_output, DISCREPANCY_COLUMNS, discrepancy_rows
    )
    summary_rows = _summarize(
        indicators=indicators,
        webapi_rows=webapi_rows,
        publication_rows=publication_rows,
        comparison_rows=comparison_rows,
    )
    summary_sha = _write_csv(summary_output, SUMMARY_COLUMNS, summary_rows)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": "H2",
        "policy": {
            "cost_class": "free",
            "geography": "national",
            "comparison_key": [
                "indicator_key",
                "series_key",
                "observed_period",
                "geo_level",
                "geo_code",
                "unit",
            ],
            "excluded_sources": ["bps_dna", "bps_sirusa", "silastik_pst"],
        },
        "inputs": [
            {"path": str(indicator_selection), "sha256": _sha256(indicator_selection)},
            {"path": str(series_selection), "sha256": _sha256(series_selection)},
            {"path": str(publication_reference), "sha256": _sha256(publication_reference)},
            {"path": str(h1_webapi_manifest), "sha256": _sha256(h1_webapi_manifest)},
            {
                "path": str(h1_publication_manifest),
                "sha256": _sha256(h1_publication_manifest),
            },
            {
                "path": str(publication_pdf),
                "sha256": publication_entry["sha256"],
                "source_id": publication_entry["source_id"],
            },
        ],
        "outputs": [
            {"path": str(webapi_output), "rows": len(webapi_rows), "sha256": webapi_sha},
            {
                "path": str(publication_output),
                "rows": len(publication_rows),
                "sha256": publication_sha,
            },
            {
                "path": str(normalized_output),
                "rows": len(normalized_rows),
                "sha256": normalized_sha,
            },
            {
                "path": str(comparison_output),
                "rows": len(comparison_rows),
                "sha256": _sha256(comparison_output),
            },
            {
                "path": str(discrepancy_output),
                "rows": len(discrepancy_rows),
                "sha256": discrepancy_sha,
            },
            {"path": str(summary_output), "rows": len(summary_rows), "sha256": summary_sha},
        ],
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    statuses = Counter(row["status"] for row in comparison_rows)
    return {
        "webapi_rows": len(webapi_rows),
        "publication_rows": len(publication_rows),
        "comparison_rows": len(comparison_rows),
        "discrepancy_rows": len(discrepancy_rows),
        "statuses": dict(statuses),
        "summary": summary_rows,
    }
