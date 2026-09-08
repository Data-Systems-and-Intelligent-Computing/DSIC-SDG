from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {
    "source_id",
    "indicator_key",
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
}
CELL_KEY = ("indicator_key", "observed_period", "geo_level", "geo_code", "unit")
OUTPUT_COLUMNS = [
    *CELL_KEY,
    "geo_name",
    "snapshot_count",
    "value_count",
    "min_value",
    "max_value",
    "absolute_spread",
    "status",
    "observations_json",
]


def compare_files(input_paths: Iterable[Path], output_path: Path) -> list[dict[str, str]]:
    paths = list(input_paths)
    if len(paths) < 2:
        raise ValueError("comparison requires at least two input files")

    rows: list[dict[str, str]] = []
    expected_snapshots: set[str] = set()
    seen_records: set[tuple[str, ...]] = set()
    for file_number, path in enumerate(paths, start=1):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path}: missing columns {sorted(missing)}")
            file_rows = list(reader)
        file_sources = {row["source_id"] for row in file_rows}
        if len(file_sources) != 1:
            raise ValueError(f"{path}: expected exactly one source_id per input snapshot")
        snapshot = f"input-{file_number}:{next(iter(file_sources))}"
        expected_snapshots.add(snapshot)
        for line_number, row in enumerate(file_rows, start=2):
            record_key = (snapshot, *(row[field] for field in CELL_KEY))
            if record_key in seen_records:
                raise ValueError(f"{path}:{line_number}: duplicate observation {record_key}")
            seen_records.add(record_key)
            try:
                row["_decimal_value"] = Decimal(row["value"])
            except InvalidOperation as error:
                raise ValueError(f"{path}:{line_number}: value is not numeric: {row['value']!r}") from error
            row["_snapshot"] = snapshot
            rows.append(row)

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in CELL_KEY)].append(row)

    output_rows: list[dict[str, str]] = []
    for key, observations in sorted(grouped.items()):
        snapshots = {row["_snapshot"] for row in observations}
        values = [row["_decimal_value"] for row in observations]
        min_value = min(values)
        max_value = max(values)
        if snapshots != expected_snapshots:
            status = "missing_snapshot"
        elif len(set(values)) == 1:
            status = "exact_match"
        else:
            status = "value_mismatch"
        serializable = [
            {field: value for field, value in row.items() if not field.startswith("_")}
            for row in sorted(observations, key=lambda item: item["_snapshot"])
        ]
        output_rows.append(
            {
                **dict(zip(CELL_KEY, key)),
                "geo_name": observations[0]["geo_name"],
                "snapshot_count": str(len(snapshots)),
                "value_count": str(len(set(values))),
                "min_value": str(min_value),
                "max_value": str(max_value),
                "absolute_spread": str(max_value - min_value),
                "status": status,
                "observations_json": json.dumps(serializable, ensure_ascii=False, sort_keys=True),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)
    return output_rows
