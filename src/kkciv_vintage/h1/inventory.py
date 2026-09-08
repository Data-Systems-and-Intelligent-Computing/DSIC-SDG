from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Iterable


ALLOWED_STATUSES = {"proposal_only", "partial", "verified", "unavailable", "blocked"}
REQUIRED_INDICATOR_COLUMNS = {
    "indicator_key",
    "sdg_code",
    "domain",
    "indicator_name",
    "unit",
    "proposed_geographies",
    "frequency",
    "proposed_sources",
    "producer",
    "webapi_domain_id",
    "webapi_variable_id",
    "sirusa_indicator_id",
    "tpb_publication_year",
    "tpb_table_or_page",
    "verified_geographies",
    "period_start",
    "period_end",
    "verification_status",
    "risk_flags",
    "assignee",
    "notes",
}
REQUIRED_SOURCE_COLUMNS = {
    "source_id",
    "channel",
    "publisher",
    "producer_policy",
    "role",
    "access_url",
    "access_type",
    "authentication",
    "format",
    "verification_status",
    "notes",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")
        rows = list(reader)
    for line_number, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(f"{path}:{line_number}: too many CSV fields")
        if any(value is None for value in row.values()):
            raise ValueError(f"{path}:{line_number}: too few CSV fields")
    return reader.fieldnames, rows


def indicator_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.csv") if path.is_file())


def validate_inventory(source_registry: Path, indicator_dir: Path) -> list[str]:
    errors: list[str] = []
    source_fields, source_rows = read_csv(source_registry)
    missing_source_fields = REQUIRED_SOURCE_COLUMNS - set(source_fields)
    if missing_source_fields:
        errors.append(f"{source_registry}: missing columns {sorted(missing_source_fields)}")

    source_ids = [row.get("source_id", "").strip() for row in source_rows]
    for duplicate, count in Counter(source_ids).items():
        if duplicate and count > 1:
            errors.append(f"{source_registry}: duplicate source_id {duplicate!r}")
    known_sources = set(source_ids)

    all_keys: list[str] = []
    for path in indicator_paths(indicator_dir):
        fields, rows = read_csv(path)
        missing_fields = REQUIRED_INDICATOR_COLUMNS - set(fields)
        if missing_fields:
            errors.append(f"{path}: missing columns {sorted(missing_fields)}")
            continue
        for line_number, row in enumerate(rows, start=2):
            key = row["indicator_key"].strip()
            all_keys.append(key)
            if not key:
                errors.append(f"{path}:{line_number}: indicator_key is empty")
            status = row["verification_status"].strip()
            if status not in ALLOWED_STATUSES:
                errors.append(f"{path}:{line_number}: invalid verification_status {status!r}")
            proposed_sources = {item for item in row["proposed_sources"].split(";") if item}
            unknown_sources = proposed_sources - known_sources
            if unknown_sources:
                errors.append(f"{path}:{line_number}: unknown sources {sorted(unknown_sources)}")
            if status == "verified":
                errors.extend(_validate_verified_row(path, line_number, row))

    for duplicate, count in Counter(all_keys).items():
        if duplicate and count > 1:
            errors.append(f"duplicate indicator_key {duplicate!r} appears {count} times")
    return errors


def _validate_verified_row(path: Path, line_number: int, row: dict[str, str]) -> list[str]:
    prefix = f"{path}:{line_number}"
    errors: list[str] = []
    required = ["producer", "verified_geographies", "period_start", "period_end"]
    for field in required:
        if not row[field].strip():
            errors.append(f"{prefix}: verified row requires {field}")

    proposed_sources = set(row["proposed_sources"].split(";"))
    if "bps_webapi" in proposed_sources:
        for field in ("webapi_domain_id", "webapi_variable_id"):
            if not row[field].strip():
                errors.append(f"{prefix}: verified WebAPI row requires {field}")
    if "bps_sirusa" in proposed_sources and not row["sirusa_indicator_id"].strip():
        errors.append(f"{prefix}: verified SIRuSa row requires sirusa_indicator_id")
    if proposed_sources & {"bps_tpb_2024", "bps_tpb_2025"}:
        for field in ("tpb_publication_year", "tpb_table_or_page"):
            if not row[field].strip():
                errors.append(f"{prefix}: verified publication row requires {field}")
    return errors


def load_indicators(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        _, file_rows = read_csv(path)
        rows.extend(file_rows)
    return rows
