from __future__ import annotations

import csv
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


VINTAGE_COLUMNS = [
    "vintage_id",
    "source_id",
    "source_channel",
    "vintage_date",
    "vintage_basis",
    "retrieved_at",
    "release_label",
    "source_manifest_path",
    "source_manifest_sha256",
]
OBSERVATION_COLUMNS = [
    "observation_id",
    "cell_id",
    "vintage_id",
    "domain",
    "indicator_key",
    "series_key",
    "observed_period",
    "period_granularity",
    "geo_level",
    "geo_code",
    "geo_name",
    "unit",
    "value_decimal",
    "value_lexeme",
    "published_decimal_places",
    "producer",
    "methodology_version",
    "source_artifact_path",
    "source_artifact_sha256",
    "source_record_id",
    "ingestion_batch_id",
    "transformation_run_id",
    "transformation_version",
    "trace_id",
    "cause_family",
    "evidence_level",
]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]
TYPE_BY_COLUMN = {
    **{column: "STRING" for column in VINTAGE_COLUMNS},
    **{column: "STRING" for column in OBSERVATION_COLUMNS},
    "vintage_date": "DATE",
    "retrieved_at": "TIMESTAMP",
    "value_decimal": "DECIMAL(38,10)",
    "published_decimal_places": "INT",
}
WEBAPI_VAR = re.compile(r"(?:^|;)var=(\d+)(?:;|$)")


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


def _id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def _manifested_output(manifest_path: Path, name: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matches = [item for item in manifest["outputs"] if Path(item["path"]).name == name]
    if len(matches) != 1:
        raise ValueError(f"{manifest_path}: expected one output named {name}")
    item = matches[0]
    path = Path(item["path"])
    if not path.exists() or _sha256(path) != item["sha256"]:
        raise ValueError(f"{manifest_path}: invalid manifested output {path}")
    if len(_read_csv(path)) != int(item["rows"]):
        raise ValueError(f"{manifest_path}: row count mismatch for {path}")
    return path, item, manifest


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("contract_version") != "h6.1":
        raise ValueError("unsupported H6 contract version")
    expected = {
        "release_vintages": VINTAGE_COLUMNS,
        "indicator_observations": OBSERVATION_COLUMNS,
    }
    for table, columns in expected.items():
        declared = contract["tables"][table]["columns"]
        names = [item[0] for item in declared]
        if names != columns:
            raise ValueError(f"{table}: contract columns do not match the implementation")
        for name, data_type, _nullable in declared:
            if TYPE_BY_COLUMN[name] != data_type:
                raise ValueError(f"{table}.{name}: expected type {TYPE_BY_COLUMN[name]}")
    if contract["tables"]["indicator_observations"]["partitioning"] != ["domain"]:
        raise ValueError("indicator observations must use the low-cardinality domain partition")
    if "source_id" in contract["identity"]["cell_id_fields"]:
        raise ValueError("cell identity must be independent of source")
    if "unit" in contract["identity"]["cell_id_fields"]:
        raise ValueError("cell identity must survive unit or methodology changes")


def validate_ddl(contract: dict[str, Any], ddl: str) -> None:
    normalized = " ".join(ddl.split()).upper()
    for table in contract["tables"].values():
        identifier = table["identifier"].upper()
        match = re.search(
            rf"CREATE TABLE IF NOT EXISTS {re.escape(identifier)} \((.*?)\) USING ICEBERG",
            normalized,
        )
        if not match:
            raise ValueError(f"DDL does not create {table['identifier']}")
        table_ddl = match.group(1)
        for name, data_type, nullable in table["columns"]:
            declaration = f"{name} {data_type}".upper()
            if not nullable:
                declaration += " NOT NULL"
            if declaration not in table_ddl:
                raise ValueError(
                    f"DDL declaration does not match contract for {table['identifier']}.{name}"
                )
    if "PARTITIONED BY (DOMAIN)" not in normalized:
        raise ValueError("DDL must partition indicator_observations by domain")


def _decimal_parts(value: str) -> tuple[str, str]:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"non-numeric observation value {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"non-finite observation value {value!r}")
    unsigned = value.lstrip("+-")
    whole, dot, fraction = unsigned.partition(".")
    integral_digits = len(whole.lstrip("0")) or 1
    if integral_digits > 28 or len(fraction) > 10:
        raise ValueError(f"{value!r} does not fit DECIMAL(38,10)")
    decimal_value = f"{parsed:.10f}"
    return decimal_value, str(len(fraction) if dot else 0)


def _source_catalogs(
    publication_manifest_path: Path, webapi_manifest_path: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    publications = json.loads(publication_manifest_path.read_text(encoding="utf-8"))
    webapi = json.loads(webapi_manifest_path.read_text(encoding="utf-8"))
    pub_files = {item["source_id"]: item for item in publications["files"]}
    api_files = {str(item["variable_id"]): item for item in webapi["files"]}
    return pub_files, api_files, publications, webapi


def project_fixture(
    *,
    traces: list[dict[str, str]],
    h4_batch_id: str,
    h5_batch_id: str,
    publication_manifest_path: Path,
    webapi_manifest_path: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    pub_files, api_files, publications, webapi = _source_catalogs(
        publication_manifest_path, webapi_manifest_path
    )
    pub_manifest_sha = _sha256(publication_manifest_path)
    api_manifest_sha = _sha256(webapi_manifest_path)
    vintages: dict[str, dict[str, str]] = {}
    observations: list[dict[str, str]] = []

    for row in traces:
        source_id = row["source_id"]
        if source_id in pub_files:
            artifact = pub_files[source_id]
            manifest_path = publication_manifest_path
            manifest_sha = pub_manifest_sha
            retrieved_at = publications["retrieved_at"]
            source_channel = "publication_pdf"
            vintage_basis = "published_release"
            release_label = artifact["title"]
        elif source_id == "bps_webapi":
            match = WEBAPI_VAR.search(row["source_record_id"])
            if not match or match.group(1) not in api_files:
                raise ValueError(f"cannot resolve WebAPI artifact for {row['source_record_id']}")
            artifact = api_files[match.group(1)]
            manifest_path = webapi_manifest_path
            manifest_sha = api_manifest_sha
            retrieved_at = webapi["retrieved_at"]
            source_channel = "webapi"
            vintage_basis = "retrieval_snapshot"
            release_label = f"WebAPI {retrieved_at}"
        else:
            raise ValueError(f"unknown H6 source {source_id!r}")

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
            raise ValueError(f"conflicting vintage dimension row {vintage_id}")
        vintages[vintage_id] = vintage

        cell_id = _id(
            row["indicator_key"],
            row["series_key"],
            row["observed_period"],
            row["geo_level"],
            row["geo_code"],
        )
        observation_id = _id(cell_id, vintage_id, row["source_record_id"])
        value_decimal, decimal_places = _decimal_parts(row["value"])
        observations.append(
            {
                "observation_id": observation_id,
                "cell_id": cell_id,
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
                "ingestion_batch_id": h4_batch_id,
                "transformation_run_id": h5_batch_id,
                "transformation_version": "h6-schema-v1",
                "trace_id": row["trace_id"],
                "cause_family": row["cause_family"],
                "evidence_level": row["evidence_level"],
            }
        )

    if len({row["observation_id"] for row in observations}) != len(observations):
        raise ValueError("H6 observation IDs are not unique")
    keys = [
        (row["cell_id"], row["vintage_id"], row["source_record_id"])
        for row in observations
    ]
    if len(set(keys)) != len(keys):
        raise ValueError("H6 logical observation key is not unique")
    vintage_ids = set(vintages)
    if {row["vintage_id"] for row in observations} - vintage_ids:
        raise ValueError("H6 observation has no vintage dimension row")
    for trace_id in {row["trace_id"] for row in observations}:
        cells = {row["cell_id"] for row in observations if row["trace_id"] == trace_id}
        if len(cells) != 1:
            raise ValueError(f"trace {trace_id} does not preserve one stable cell identity")

    return (
        sorted(vintages.values(), key=lambda row: (row["vintage_date"], row["source_id"])),
        sorted(observations, key=lambda row: (row["cell_id"], row["vintage_id"])),
    )


def run_h6(
    *,
    contract_path: Path,
    ddl_path: Path,
    h5_manifest_path: Path,
    publication_manifest_path: Path,
    webapi_manifest_path: Path,
    vintages_output: Path,
    observations_output: Path,
    validation_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    validate_ddl(contract, ddl_path.read_text(encoding="utf-8"))
    trace_path, trace_item, h5_manifest = _manifested_output(
        h5_manifest_path, "h5-revision-traces.csv"
    )
    if h5_manifest["stage"] != "H5" or h5_manifest["gate_g1"]["overall_gate_status"] != "passed":
        raise ValueError("H6 requires a passed H5 Gate G1 manifest")
    h4_manifest_path = Path(
        next(item["path"] for item in h5_manifest["inputs"] if "h4-ingestion" in item["path"])
    )
    h4_manifest = json.loads(h4_manifest_path.read_text(encoding="utf-8"))
    vintages, observations = project_fixture(
        traces=_read_csv(trace_path),
        h4_batch_id=h4_manifest["batch_id"],
        h5_batch_id=h5_manifest["batch_id"],
        publication_manifest_path=publication_manifest_path,
        webapi_manifest_path=webapi_manifest_path,
    )
    cells = {row["cell_id"] for row in observations}
    validation = [
        {"invariant": "schema_contract", "status": "passed", "checked_rows": "2", "detail": "two table definitions match h6.1"},
        {"invariant": "explicit_vintage_fk", "status": "passed", "checked_rows": str(len(observations)), "detail": f"all rows reference {len(vintages)} vintage dimension rows"},
        {"invariant": "stable_source_independent_cell_id", "status": "passed", "checked_rows": str(len(cells)), "detail": "one cell_id per H5 trace across sources"},
        {"invariant": "lossless_value_lexeme", "status": "passed", "checked_rows": str(len(observations)), "detail": "published lexeme retained beside exact DECIMAL(38,10)"},
        {"invariant": "unique_observation_identity", "status": "passed", "checked_rows": str(len(observations)), "detail": "no duplicate observation_id or logical key"},
        {"invariant": "derived_current_rule", "status": "passed", "checked_rows": str(len(cells)), "detail": "current is ordered from vintage_date and is not stored"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (vintages_output, VINTAGE_COLUMNS, vintages),
        (observations_output, OBSERVATION_COLUMNS, observations),
        (validation_output, VALIDATION_COLUMNS, validation),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H6",
        "schema_status": "validated",
        "contract_version": contract["contract_version"],
        "fixture": {
            "source_stage": "H5",
            "vintage_rows": len(vintages),
            "observation_rows": len(observations),
            "cell_count": len(cells),
            "lossless_projection": True,
        },
        "iceberg_targets": {
            name: table["identifier"] for name, table in contract["tables"].items()
        },
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(ddl_path), "sha256": _sha256(ddl_path)},
            {"path": str(h5_manifest_path), "sha256": _sha256(h5_manifest_path)},
            {"path": str(trace_path), "rows": trace_item["rows"], "sha256": trace_item["sha256"]},
            {"path": str(publication_manifest_path), "sha256": _sha256(publication_manifest_path)},
            {"path": str(webapi_manifest_path), "sha256": _sha256(webapi_manifest_path)},
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "contract_version": contract["contract_version"],
        "vintage_rows": len(vintages),
        "observation_rows": len(observations),
        "cell_count": len(cells),
        "status": manifest["schema_status"],
    }
