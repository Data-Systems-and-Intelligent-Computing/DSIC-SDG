from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kkciv_vintage.h4.pipeline import CORE_CAUSES, EVENT_COLUMNS


EVIDENCE_COLUMNS = [
    "event_id",
    "evidence_kind",
    "promoted_classification",
    "promoted_cause_family",
    "corroborating_source_id",
    "corroborating_release_date",
    "corroborating_value",
    "published_status",
    "evidence_locator",
    "evidence_note",
]
CONFIRMED_EVENT_COLUMNS = [
    *EVENT_COLUMNS,
    "original_classification",
    "original_cause_family",
    "original_evidence_level",
    "promoted",
    "evidence_kind",
    "evidence_locator",
    "evidence_note",
]
TRACE_COLUMNS = [
    "trace_id",
    "event_id",
    "trace_type",
    "domain",
    "indicator_key",
    "series_key",
    "observed_period",
    "geo_level",
    "geo_code",
    "geo_name",
    "unit",
    "cause_family",
    "evidence_level",
    "vintage_order",
    "source_id",
    "release_date",
    "value",
    "producer",
    "methodology_version",
    "source_record_id",
    "evidence_note",
]
GATE_COLUMNS = ["criterion", "status", "value", "threshold", "evidence"]


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


def _decimal(value: str, context: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{context}: non-numeric value {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"{context}: non-finite value {value!r}")
    return parsed


def _verified_h4_outputs(manifest_path: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "H4":
        raise ValueError(f"{manifest_path}: expected an H4 manifest")
    outputs: dict[str, Path] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists():
            raise FileNotFoundError(f"manifested H4 output is missing: {path}")
        if _sha256(path) != item["sha256"]:
            raise ValueError(f"checksum mismatch for manifested H4 output {path}")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested H4 output {path}")
        outputs[path.name] = path
    required = {"h4-classified-events.csv", "h4-ingested-observations.csv"}
    if missing := required - outputs.keys():
        raise ValueError(f"{manifest_path}: missing required outputs {sorted(missing)}")
    return outputs, manifest


def _publication_releases(manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    releases = {item["source_id"]: item for item in manifest["files"]}
    required = {"bps_tpb_2024", "bps_tpb_2025"}
    if missing := required - releases.keys():
        raise ValueError(f"{manifest_path}: missing publications {sorted(missing)}")
    return releases


def _load_evidence(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EVIDENCE_COLUMNS:
            raise ValueError(f"{path}: expected columns {EVIDENCE_COLUMNS}")
        rows = list(reader)
    evidence = {row["event_id"]: row for row in rows}
    if len(evidence) != len(rows):
        raise ValueError(f"{path}: duplicate event_id")
    return evidence


def _observation_index(rows: list[dict[str, str]]) -> dict[tuple[str, ...], dict[str, str]]:
    index: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = (
            row["input_dataset"],
            row["source_id"],
            row["indicator_key"],
            row["series_key"],
            row["observed_period"],
            row["geo_level"],
            row["geo_code"],
            row["unit"],
        )
        if key in index:
            raise ValueError(f"duplicate H4 observation key {key}")
        index[key] = row
    return index


def _find_observation(
    index: dict[tuple[str, ...], dict[str, str]],
    event: dict[str, str],
    *,
    dataset: str,
    source_id: str,
) -> dict[str, str]:
    key = (
        dataset,
        source_id,
        event["indicator_key"],
        event["series_key"],
        event["observed_period"],
        event["geo_level"],
        event["geo_code"],
        event["unit"],
    )
    try:
        return index[key]
    except KeyError as exc:
        raise ValueError(f"no H4 observation for {key}") from exc


def _trace_row(
    event: dict[str, str],
    observation: dict[str, str],
    *,
    trace_type: str,
    cause_family: str,
    vintage_order: int,
    evidence_note: str,
) -> dict[str, str]:
    return {
        "trace_id": event["event_id"],
        "event_id": event["event_id"],
        "trace_type": trace_type,
        "domain": event["domain"],
        "indicator_key": event["indicator_key"],
        "series_key": event["series_key"],
        "observed_period": event["observed_period"],
        "geo_level": event["geo_level"],
        "geo_code": event["geo_code"],
        "geo_name": observation["geo_name"],
        "unit": event["unit"],
        "cause_family": cause_family,
        "evidence_level": "observed",
        "vintage_order": str(vintage_order),
        "source_id": observation["source_id"],
        "release_date": observation["release_date"],
        "value": observation["value"],
        "producer": observation["producer"],
        "methodology_version": observation["methodology_version"],
        "source_record_id": observation["source_record_id"],
        "evidence_note": evidence_note,
    }


def consolidate_h5(
    *,
    h4_events: list[dict[str, str]],
    h4_observations: list[dict[str, str]],
    evidence: dict[str, dict[str, str]],
    publication_releases: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    events_by_id = {row["event_id"]: row for row in h4_events}
    if len(events_by_id) != len(h4_events):
        raise ValueError("H4 event IDs are not unique")
    if unknown := evidence.keys() - events_by_id.keys():
        raise ValueError(f"evidence refers to unknown H4 events {sorted(unknown)}")

    observations = _observation_index(h4_observations)
    confirmed: list[dict[str, str]] = []
    traces: list[dict[str, str]] = []

    for event in h4_events:
        decision = evidence.get(event["event_id"])
        final = dict(event)
        final.update(
            {
                "original_classification": event["classification"],
                "original_cause_family": event["cause_family"],
                "original_evidence_level": event["evidence_level"],
                "promoted": "no",
                "evidence_kind": "",
                "evidence_locator": "",
                "evidence_note": "",
            }
        )
        if decision:
            if event["evidence_level"] != "candidate":
                raise ValueError(f"{event['event_id']}: only candidate evidence can be promoted")
            if decision["promoted_cause_family"] not in CORE_CAUSES:
                raise ValueError(
                    f"{event['event_id']}: promoted cause must be a Gate G1 core cause"
                )
            final.update(
                {
                    "classification": decision["promoted_classification"],
                    "cause_family": decision["promoted_cause_family"],
                    "evidence_level": "observed",
                    "promoted": "yes",
                    "evidence_kind": decision["evidence_kind"],
                    "evidence_locator": decision["evidence_locator"],
                    "evidence_note": decision["evidence_note"],
                }
            )

            if decision["evidence_kind"] == "provisional_publication_to_later_snapshot":
                if event["classification"] != "vintage_candidate":
                    raise ValueError(f"{event['event_id']}: expected vintage_candidate")
                if event["observed_period"] not in {"2022", "2023"}:
                    raise ValueError(f"{event['event_id']}: period is not marked provisional")
                expected_status = "provisional" if event["observed_period"] == "2022" else "very_provisional"
                if decision["published_status"] != expected_status:
                    raise ValueError(
                        f"{event['event_id']}: expected published_status {expected_status}"
                    )
                values = json.loads(event["source_values_json"])
                old_value = _decimal(values["bps_tpb_2024"], event["event_id"])
                current_value = _decimal(values["bps_webapi"], event["event_id"])
                corroborating_value = _decimal(
                    decision["corroborating_value"], event["event_id"]
                )
                if corroborating_value != old_value:
                    raise ValueError(
                        f"{event['event_id']}: TPB 2025 does not corroborate the published value"
                    )
                if current_value == old_value:
                    raise ValueError(f"{event['event_id']}: later snapshot did not change")
                if decision["corroborating_source_id"] != "bps_tpb_2025":
                    raise ValueError(f"{event['event_id']}: expected TPB 2025 corroboration")
                if decision["corroborating_release_date"] != publication_releases[
                    "bps_tpb_2025"
                ]["release_date"]:
                    raise ValueError(f"{event['event_id']}: TPB 2025 release date mismatch")

                older = _find_observation(
                    observations,
                    event,
                    dataset="h3_province_publication",
                    source_id="bps_tpb_2024",
                )
                current = _find_observation(
                    observations,
                    event,
                    dataset="h3_province_webapi",
                    source_id="bps_webapi",
                )
                if _decimal(older["value"], event["event_id"]) != old_value:
                    raise ValueError(f"{event['event_id']}: H4 publication value mismatch")
                if _decimal(current["value"], event["event_id"]) != current_value:
                    raise ValueError(f"{event['event_id']}: H4 WebAPI value mismatch")
                corroborating = {
                    **older,
                    "source_id": decision["corroborating_source_id"],
                    "release_date": decision["corroborating_release_date"],
                    "value": decision["corroborating_value"],
                    "methodology_version": f"tpb-2025-appendix-{decision['published_status']}",
                    "source_record_id": decision["evidence_locator"],
                }
                note = decision["evidence_note"]
                for order, observation in enumerate((older, corroborating, current), start=1):
                    traces.append(
                        _trace_row(
                            event,
                            observation,
                            trace_type="provisional_to_revised_snapshot",
                            cause_family="vintage",
                            vintage_order=order,
                            evidence_note=note,
                        )
                    )
            elif decision["evidence_kind"] != "published_definition_change":
                raise ValueError(
                    f"{event['event_id']}: unsupported evidence kind {decision['evidence_kind']!r}"
                )
        confirmed.append(final)

    # Freeze every direct value change between the two dated publications. This
    # includes the forest-cover methodology change promoted above.
    for event in h4_events:
        values = json.loads(event["source_values_json"])
        if not {"bps_tpb_2024", "bps_tpb_2025"}.issubset(values):
            continue
        if _decimal(values["bps_tpb_2024"], event["event_id"]) == _decimal(
            values["bps_tpb_2025"], event["event_id"]
        ):
            continue
        final = next(row for row in confirmed if row["event_id"] == event["event_id"])
        if final["evidence_level"] != "observed":
            raise ValueError(f"{event['event_id']}: dated publication change is not observed")
        note = final["evidence_note"] or event["classification_note"]
        for order, source_id in enumerate(("bps_tpb_2024", "bps_tpb_2025"), start=1):
            observation = _find_observation(
                observations,
                event,
                dataset="h3_release_reconciliation",
                source_id=source_id,
            )
            if _decimal(observation["value"], event["event_id"]) != _decimal(
                values[source_id], event["event_id"]
            ):
                raise ValueError(f"{event['event_id']}: release observation value mismatch")
            traces.append(
                _trace_row(
                    event,
                    observation,
                    trace_type="published_release_change",
                    cause_family=final["cause_family"],
                    vintage_order=order,
                    evidence_note=note,
                )
            )

    confirmed.sort(key=lambda row: row["event_id"])
    traces.sort(key=lambda row: (row["trace_id"], int(row["vintage_order"])))
    return confirmed, traces


def run_h5(
    *,
    h4_manifest_path: Path,
    publication_manifest_path: Path,
    evidence_path: Path,
    events_output: Path,
    traces_output: Path,
    gate_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    outputs, h4_manifest = _verified_h4_outputs(h4_manifest_path)
    publication_releases = _publication_releases(publication_manifest_path)
    evidence = _load_evidence(evidence_path)
    confirmed, traces = consolidate_h5(
        h4_events=_read_csv(outputs["h4-classified-events.csv"]),
        h4_observations=_read_csv(outputs["h4-ingested-observations.csv"]),
        evidence=evidence,
        publication_releases=publication_releases,
    )

    total_events = len(confirmed)
    confirmed_core = sum(
        row["cause_family"] in CORE_CAUSES and row["evidence_level"] == "observed"
        for row in confirmed
    )
    confirmed_rate = Decimal(confirmed_core) / Decimal(total_events)
    threshold = Decimal("0.70")
    direct_traces = {
        row["trace_id"] for row in traces if row["trace_type"] == "published_release_change"
    }
    trace_ids = {row["trace_id"] for row in traces}
    criterion_1_passed = bool(h4_manifest["gate_g1"]["criterion_1_passed"])
    criterion_2_passed = confirmed_rate >= threshold
    criterion_3_passed = len(direct_traces) > 0
    gate_status = "passed" if all(
        (criterion_1_passed, criterion_2_passed, criterion_3_passed)
    ) else "failed"

    gate_rows = [
        {
            "criterion": "G1.1_mismatch_in_at_least_three_domains",
            "status": "passed" if criterion_1_passed else "failed",
            "value": str(len(h4_manifest["gate_g1"]["criterion_1_mismatch_domains"])),
            "threshold": "3",
            "evidence": ";".join(h4_manifest["gate_g1"]["criterion_1_mismatch_domains"]),
        },
        {
            "criterion": "G1.2_confirmed_core_cause_share",
            "status": "passed" if criterion_2_passed else "failed",
            "value": f"{confirmed_rate:.4f}",
            "threshold": "0.70",
            "evidence": f"{confirmed_core}/{total_events} confirmed events",
        },
        {
            "criterion": "G1.3_observable_intertemporal_revision_trace",
            "status": "passed" if criterion_3_passed else "failed",
            "value": str(len(direct_traces)),
            "threshold": "1",
            "evidence": f"{len(trace_ids)} total frozen traces; {len(traces)} vintage rows",
        },
    ]

    batch_digest = hashlib.sha256(
        (
            _sha256(h4_manifest_path)
            + _sha256(publication_manifest_path)
            + _sha256(evidence_path)
        ).encode("ascii")
    ).hexdigest()
    batch_id = f"h5-{batch_digest[:16]}"
    written_outputs = []
    for path, columns, rows in (
        (events_output, CONFIRMED_EVENT_COLUMNS, confirmed),
        (traces_output, TRACE_COLUMNS, traces),
        (gate_output, GATE_COLUMNS, gate_rows),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H5",
        "batch_id": batch_id,
        "generated_from_snapshot_at": h4_manifest["generated_from_snapshot_at"],
        "policy": {
            "gate_g1_explanation_threshold": str(threshold),
            "promotion_requires_dated_corroboration": True,
            "pdf_payloads_are_reproducible_from_h1_manifest": True,
            "cost_class": "free",
        },
        "gate_g1": {
            "criterion_1_passed": criterion_1_passed,
            "criterion_1_mismatch_domains": h4_manifest["gate_g1"][
                "criterion_1_mismatch_domains"
            ],
            "criterion_2_total_events": total_events,
            "criterion_2_confirmed_core_events": confirmed_core,
            "criterion_2_confirmed_rate": f"{confirmed_rate:.4f}",
            "criterion_2_confirmed_passed": criterion_2_passed,
            "criterion_3_direct_publication_traces": len(direct_traces),
            "criterion_3_total_frozen_traces": len(trace_ids),
            "criterion_3_passed": criterion_3_passed,
            "overall_gate_status": gate_status,
        },
        "iceberg_target": {
            "catalog": "kkciv",
            "namespace": "gate1",
            "table": "h5_revision_trace",
            "verification_command": "make h5-iceberg",
        },
        "inputs": [
            {"path": str(h4_manifest_path), "sha256": _sha256(h4_manifest_path)},
            {
                "path": str(publication_manifest_path),
                "sha256": _sha256(publication_manifest_path),
            },
            {"path": str(evidence_path), "rows": len(evidence), "sha256": _sha256(evidence_path)},
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "batch_id": batch_id,
        "event_rows": total_events,
        "promoted_events": len(evidence),
        "confirmed_core_events": confirmed_core,
        "confirmed_rate": f"{confirmed_rate:.4f}",
        "trace_count": len(trace_ids),
        "trace_rows": len(traces),
        "gate_status": gate_status,
    }

