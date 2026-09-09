from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


NODE_TYPES = [
    "source_manifest",
    "source_artifact",
    "source_record",
    "vintage",
    "ingestion_batch",
    "transformation_run",
    "transformation_version",
    "observation",
    "indicator_cell",
]
RELATIONSHIPS = [
    "manifest_declares_artifact",
    "manifest_declares_vintage",
    "artifact_contains_record",
    "record_sources_observation",
    "vintage_contextualizes_observation",
    "ingestion_batch_feeds_run",
    "transformation_run_derives_observation",
    "transformation_version_projects_observation",
    "observation_materializes_cell",
]
NODE_COLUMNS = [
    "node_id",
    "node_type",
    "natural_key",
    "label",
    "domain",
    "source_id",
    "vintage_id",
    "path",
    "sha256",
]
EDGE_COLUMNS = [
    "edge_id",
    "from_node_id",
    "to_node_id",
    "relationship",
    "observation_id",
    "cell_id",
    "evidence_basis",
]
PATH_COLUMNS = [
    "lineage_path_id",
    "cell_id",
    "observation_id",
    "domain",
    "vintage_id",
    "source_id",
    "manifest_node_id",
    "artifact_node_id",
    "source_record_node_id",
    "observation_node_id",
    "cell_node_id",
    "ingestion_batch_node_id",
    "transformation_run_node_id",
    "transformation_version_node_id",
    "raw_source_record_id",
    "raw_locator_occurrences",
    "source_record_resolution",
    "core_hop_count",
    "complete",
]
VALIDATION_COLUMNS = ["invariant", "status", "checked_rows", "detail"]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def _node_id(node_type: str, *parts: str) -> str:
    return f"{node_type}:{_id(node_type, *parts)}"


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
    if contract.get("contract_version") != "h6c.1" or contract.get("track") != "C":
        raise ValueError("unsupported H6C lineage contract")
    if contract["graph"]["direction"] != "upstream_to_downstream":
        raise ValueError("H6C lineage must use one declared edge direction")
    if contract["graph"]["node_types"] != NODE_TYPES:
        raise ValueError("H6C node types do not match the implementation")
    if contract["graph"]["relationships"] != RELATIONSHIPS:
        raise ValueError("H6C relationships do not match the implementation")
    resolution = contract["resolution"]
    if resolution["matching"] != "exact_identifiers_only" or resolution["fuzzy_matching_allowed"]:
        raise ValueError("H6C must not use fuzzy lineage matching")
    expected_record_fields = [
        "source_artifact_sha256",
        "source_record_id",
        "indicator_key",
        "series_key",
        "observed_period",
        "geo_level",
        "geo_code",
    ]
    if contract["identity"]["source_record_node_fields"] != expected_record_fields:
        raise ValueError("H6C source record identity must resolve geographic table rows")


def _manifested_h6_outputs(
    manifest_path: Path,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "H6" or manifest.get("schema_status") != "validated":
        raise ValueError("H6C requires a validated H6 schema manifest")
    outputs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested H6 output {path}")
        if len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested H6 output {path}")
        outputs[path.name] = (path, item)
    try:
        vintage_path, vintage_item = outputs["h6-release-vintages.csv"]
        observation_path, observation_item = outputs["h6-indicator-observations.csv"]
    except KeyError as exc:
        raise ValueError("H6 manifest lacks lineage inputs") from exc
    return vintage_path, vintage_item, observation_path, observation_item


def build_lineage(
    vintages: list[dict[str, str]], observations: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    vintage_by_id = {row["vintage_id"]: row for row in vintages}
    if len(vintage_by_id) != len(vintages):
        raise ValueError("H6C vintage identities are not unique")
    if len({row["observation_id"] for row in observations}) != len(observations):
        raise ValueError("H6C observation identities are not unique")
    if unknown := {row["vintage_id"] for row in observations} - vintage_by_id.keys():
        raise ValueError(f"H6C observations reference unknown vintages {sorted(unknown)}")

    raw_locator_counts = Counter(
        (row["source_artifact_sha256"], row["source_record_id"]) for row in observations
    )
    nodes: dict[str, dict[str, str]] = {}
    edges: dict[str, dict[str, str]] = {}
    paths: list[dict[str, str]] = []

    def add_node(
        node_id: str,
        node_type: str,
        natural_key: str,
        label: str,
        *,
        domain: str = "",
        source_id: str = "",
        vintage_id: str = "",
        path: str = "",
        sha256: str = "",
    ) -> None:
        node = {
            "node_id": node_id,
            "node_type": node_type,
            "natural_key": natural_key,
            "label": label,
            "domain": domain,
            "source_id": source_id,
            "vintage_id": vintage_id,
            "path": path,
            "sha256": sha256,
        }
        if node_id in nodes and nodes[node_id] != node:
            raise ValueError(f"conflicting H6C node {node_id}")
        nodes[node_id] = node

    def add_edge(
        relationship: str,
        from_node_id: str,
        to_node_id: str,
        *,
        observation_id: str = "",
        cell_id: str = "",
        evidence_basis: str,
    ) -> None:
        edge_id = f"edge:{_id(relationship, from_node_id, to_node_id)}"
        edge = {
            "edge_id": edge_id,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "relationship": relationship,
            "observation_id": observation_id,
            "cell_id": cell_id,
            "evidence_basis": evidence_basis,
        }
        if edge_id in edges and edges[edge_id] != edge:
            raise ValueError(f"conflicting H6C edge {edge_id}")
        edges[edge_id] = edge

    for observation in sorted(observations, key=lambda row: row["observation_id"]):
        vintage = vintage_by_id[observation["vintage_id"]]
        source_id = vintage["source_id"]
        record_parts = [
            observation["source_artifact_sha256"],
            observation["source_record_id"],
            observation["indicator_key"],
            observation["series_key"],
            observation["observed_period"],
            observation["geo_level"],
            observation["geo_code"],
        ]
        record_key = json.dumps(record_parts, ensure_ascii=False, separators=(",", ":"))
        manifest_node = _node_id(
            "source_manifest", vintage["source_manifest_path"], vintage["source_manifest_sha256"]
        )
        artifact_node = _node_id(
            "source_artifact",
            observation["source_artifact_path"],
            observation["source_artifact_sha256"],
        )
        record_node = _node_id("source_record", *record_parts)
        vintage_node = _node_id("vintage", observation["vintage_id"])
        batch_node = _node_id("ingestion_batch", observation["ingestion_batch_id"])
        run_node = _node_id("transformation_run", observation["transformation_run_id"])
        version_node = _node_id(
            "transformation_version", observation["transformation_version"]
        )
        observation_node = _node_id("observation", observation["observation_id"])
        cell_node = _node_id("indicator_cell", observation["cell_id"])

        add_node(
            manifest_node,
            "source_manifest",
            vintage["source_manifest_path"],
            Path(vintage["source_manifest_path"]).name,
            path=vintage["source_manifest_path"],
            sha256=vintage["source_manifest_sha256"],
        )
        add_node(
            artifact_node,
            "source_artifact",
            observation["source_artifact_path"],
            Path(observation["source_artifact_path"]).name,
            source_id=source_id,
            path=observation["source_artifact_path"],
            sha256=observation["source_artifact_sha256"],
        )
        add_node(
            record_node,
            "source_record",
            record_key,
            observation["source_record_id"],
            domain=observation["domain"],
            source_id=source_id,
            vintage_id=observation["vintage_id"],
        )
        add_node(
            vintage_node,
            "vintage",
            observation["vintage_id"],
            f"{source_id} {vintage['vintage_date']}",
            source_id=source_id,
            vintage_id=observation["vintage_id"],
        )
        add_node(
            batch_node,
            "ingestion_batch",
            observation["ingestion_batch_id"],
            observation["ingestion_batch_id"],
        )
        add_node(
            run_node,
            "transformation_run",
            observation["transformation_run_id"],
            observation["transformation_run_id"],
        )
        add_node(
            version_node,
            "transformation_version",
            observation["transformation_version"],
            observation["transformation_version"],
        )
        add_node(
            observation_node,
            "observation",
            observation["observation_id"],
            observation["observation_id"],
            domain=observation["domain"],
            source_id=source_id,
            vintage_id=observation["vintage_id"],
        )
        add_node(
            cell_node,
            "indicator_cell",
            observation["cell_id"],
            "|".join(
                [
                    observation["indicator_key"],
                    observation["observed_period"],
                    observation["geo_code"],
                ]
            ),
            domain=observation["domain"],
        )

        add_edge(
            "manifest_declares_artifact",
            manifest_node,
            artifact_node,
            evidence_basis="explicit manifest path and artifact checksum",
        )
        add_edge(
            "manifest_declares_vintage",
            manifest_node,
            vintage_node,
            evidence_basis="explicit vintage manifest path and checksum",
        )
        add_edge(
            "artifact_contains_record",
            artifact_node,
            record_node,
            observation_id=observation["observation_id"],
            cell_id=observation["cell_id"],
            evidence_basis="artifact checksum plus exact source locator and H6 cell coordinates",
        )
        add_edge(
            "record_sources_observation",
            record_node,
            observation_node,
            observation_id=observation["observation_id"],
            cell_id=observation["cell_id"],
            evidence_basis="H6 source_record_id carried by the observation",
        )
        add_edge(
            "vintage_contextualizes_observation",
            vintage_node,
            observation_node,
            observation_id=observation["observation_id"],
            cell_id=observation["cell_id"],
            evidence_basis="H6 vintage_id foreign key",
        )
        add_edge(
            "ingestion_batch_feeds_run",
            batch_node,
            run_node,
            evidence_basis="H6 ingestion_batch_id and transformation_run_id",
        )
        add_edge(
            "transformation_run_derives_observation",
            run_node,
            observation_node,
            observation_id=observation["observation_id"],
            cell_id=observation["cell_id"],
            evidence_basis="H6 transformation_run_id",
        )
        add_edge(
            "transformation_version_projects_observation",
            version_node,
            observation_node,
            observation_id=observation["observation_id"],
            cell_id=observation["cell_id"],
            evidence_basis="H6 transformation_version",
        )
        add_edge(
            "observation_materializes_cell",
            observation_node,
            cell_node,
            observation_id=observation["observation_id"],
            cell_id=observation["cell_id"],
            evidence_basis="H6 stable cell_id",
        )

        occurrences = raw_locator_counts[
            (observation["source_artifact_sha256"], observation["source_record_id"])
        ]
        paths.append(
            {
                "lineage_path_id": f"path:{_id(observation['observation_id'], observation['cell_id'])}",
                "cell_id": observation["cell_id"],
                "observation_id": observation["observation_id"],
                "domain": observation["domain"],
                "vintage_id": observation["vintage_id"],
                "source_id": source_id,
                "manifest_node_id": manifest_node,
                "artifact_node_id": artifact_node,
                "source_record_node_id": record_node,
                "observation_node_id": observation_node,
                "cell_node_id": cell_node,
                "ingestion_batch_node_id": batch_node,
                "transformation_run_node_id": run_node,
                "transformation_version_node_id": version_node,
                "raw_source_record_id": observation["source_record_id"],
                "raw_locator_occurrences": str(occurrences),
                "source_record_resolution": "composite_with_cell_coordinates"
                if occurrences > 1
                else "raw_locator_unique_within_artifact",
                "core_hop_count": "4",
                "complete": "yes",
            }
        )

    node_rows = sorted(nodes.values(), key=lambda row: (row["node_type"], row["node_id"]))
    edge_rows = sorted(edges.values(), key=lambda row: (row["relationship"], row["edge_id"]))
    paths.sort(key=lambda row: (row["cell_id"], row["observation_id"]))
    node_types = {row["node_id"]: row["node_type"] for row in node_rows}
    for edge in edge_rows:
        if edge["from_node_id"] not in node_types or edge["to_node_id"] not in node_types:
            raise ValueError("H6C edge references an unknown node")
    ambiguous_keys = {key for key, count in raw_locator_counts.items() if count > 1}
    metrics = {
        "node_count": len(node_rows),
        "edge_count": len(edge_rows),
        "path_count": len(paths),
        "cell_count": len({row["cell_id"] for row in observations}),
        "source_record_count": sum(row["node_type"] == "source_record" for row in node_rows),
        "raw_locator_collision_groups": len(ambiguous_keys),
        "raw_locator_collision_observations": sum(raw_locator_counts[key] for key in ambiguous_keys),
    }
    if metrics["path_count"] != len(observations) or any(row["complete"] != "yes" for row in paths):
        raise ValueError("H6C does not provide one complete path per observation")
    if metrics["source_record_count"] != len(observations):
        raise ValueError("H6C composite record identities are not observation-exact")
    return node_rows, edge_rows, paths, metrics


def run_h6c(
    *,
    contract_path: Path,
    h6_manifest_path: Path,
    nodes_output: Path,
    edges_output: Path,
    paths_output: Path,
    validation_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    vintage_path, vintage_item, observation_path, observation_item = _manifested_h6_outputs(
        h6_manifest_path
    )
    observations = _read_csv(observation_path)
    nodes, edges, paths, metrics = build_lineage(_read_csv(vintage_path), observations)
    per_cell = Counter(row["cell_id"] for row in paths)
    completeness = len(paths) / len(observations)
    validation = [
        {"invariant": "graph_contract", "status": "passed", "checked_rows": str(len(NODE_TYPES) + len(RELATIONSHIPS)), "detail": "nine node types and nine directed relationships match h6c.1"},
        {"invariant": "unique_graph_identities", "status": "passed", "checked_rows": str(metrics["node_count"] + metrics["edge_count"]), "detail": "all node_id and edge_id values are deterministic and unique"},
        {"invariant": "complete_core_paths", "status": "passed", "checked_rows": str(metrics["path_count"]), "detail": "one four-hop manifest-to-cell path per H6 observation"},
        {"invariant": "exact_source_record_resolution", "status": "passed", "checked_rows": str(metrics["source_record_count"]), "detail": "artifact locator plus explicit cell coordinates resolves every source record node"},
        {"invariant": "raw_locator_collisions_disclosed", "status": "passed", "checked_rows": str(metrics["raw_locator_collision_observations"]), "detail": f"{metrics['raw_locator_collision_groups']} reused publication locators are retained and resolved"},
        {"invariant": "cell_reachability", "status": "passed", "checked_rows": str(metrics["cell_count"]), "detail": f"every cell has {min(per_cell.values())}-{max(per_cell.values())} manifested source paths"},
        {"invariant": "no_fuzzy_matching", "status": "passed", "checked_rows": str(metrics["edge_count"]), "detail": "all edges derive from explicit H6 identifiers, paths, checksums, or foreign keys"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (nodes_output, NODE_COLUMNS, nodes),
        (edges_output, EDGE_COLUMNS, edges),
        (paths_output, PATH_COLUMNS, paths),
        (validation_output, VALIDATION_COLUMNS, validation),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H6",
        "track": "C",
        "lineage_status": "validated",
        "contract_version": contract["contract_version"],
        "graph": {
            **metrics,
            "completeness_rate": f"{completeness:.4f}",
            "minimum_paths_per_cell": min(per_cell.values()),
            "maximum_paths_per_cell": max(per_cell.values()),
            "matching": contract["resolution"]["matching"],
        },
        "inputs": [
            {"path": str(contract_path), "sha256": _sha256(contract_path)},
            {"path": str(h6_manifest_path), "sha256": _sha256(h6_manifest_path)},
            {"path": str(vintage_path), "rows": vintage_item["rows"], "sha256": vintage_item["sha256"]},
            {"path": str(observation_path), "rows": observation_item["rows"], "sha256": observation_item["sha256"]},
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**metrics, "completeness_rate": f"{completeness:.4f}", "status": "validated"}
