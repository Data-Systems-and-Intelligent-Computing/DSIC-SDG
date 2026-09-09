from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


BASE_NODE_COLUMNS = [
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
NODE_COLUMNS = [
    *BASE_NODE_COLUMNS,
    "treatment_id",
    "observation_id",
    "decision",
    "addressable",
]
BASE_EDGE_COLUMNS = [
    "edge_id",
    "from_node_id",
    "to_node_id",
    "relationship",
    "observation_id",
    "cell_id",
    "evidence_basis",
]
EDGE_COLUMNS = [*BASE_EDGE_COLUMNS, "treatment_id"]
TREATMENT_LINEAGE_COLUMNS = [
    "treatment_lineage_id",
    "treatment_id",
    "cell_id",
    "requested_observation_id",
    "source_lineage_path_id",
    "source_record_node_id",
    "observation_node_id",
    "treatment_run_node_id",
    "treatment_decision_node_id",
    "treatment_output_node_id",
    "output_observation_id",
    "decision",
    "requested_addressable",
    "treatment_manifest_path",
    "treatment_manifest_sha256",
    "complete",
]
LITERATURE_COLUMNS = [
    "source_key",
    "title",
    "sections",
    "prior_occurrences",
    "evidence_url",
    "evidence_authority",
    "identifier",
    "canonical_year",
    "canonical_venue",
    "verification_level",
    "verified_at",
    "metadata_correction",
    "relevance_note",
    "verification_result",
]
COMPONENT_COLUMNS = [
    "component",
    "status",
    "decision_basis",
    "current_evidence",
    "activation_trigger",
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
    if (
        contract.get("contract_version") != "h7c.1"
        or contract.get("stage") != "H7"
        or contract.get("track") != "C"
    ):
        raise ValueError("unsupported H7C contract")
    literature = contract["literature_verification"]
    if literature["expected_unique_sources"] != 15 or literature["expected_prior_occurrences"] != 18:
        raise ValueError("H7C literature scope must preserve the frozen daftar inventory")
    extension = contract["lineage_extension"]
    if extension["base_contract_version"] != "h6c.1":
        raise ValueError("H7C must extend the frozen H6C graph")
    if extension["treatments"] != ["B0", "B2"]:
        raise ValueError("H7C must cover both implemented H7 treatments")
    if extension["matching"] != "exact_identifiers_only" or extension["fuzzy_matching_allowed"]:
        raise ValueError("H7C must not use fuzzy lineage matching")
    if extension["new_node_types"] != [
        "treatment_run",
        "treatment_decision",
        "treatment_output",
    ]:
        raise ValueError("H7C node extension does not match the implementation")
    if extension["new_relationships"] != [
        "observation_enters_treatment",
        "treatment_run_evaluates_candidate",
        "decision_resolves_to_output",
        "output_serves_cell",
    ]:
        raise ValueError("H7C relationship extension does not match the implementation")


def _verified_manifest(
    manifest_path: Path,
    *,
    expected_stage: str,
    expected_track: str | None = None,
    expected_treatment: str | None = None,
) -> tuple[dict[str, Any], dict[str, Path]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != expected_stage:
        raise ValueError(f"unexpected stage in {manifest_path}")
    if expected_track is not None and manifest.get("track") != expected_track:
        raise ValueError(f"unexpected track in {manifest_path}")
    if expected_treatment is not None and manifest.get("treatment_id") != expected_treatment:
        raise ValueError(f"unexpected treatment in {manifest_path}")
    paths: dict[str, Path] = {}
    for item in [*manifest.get("inputs", []), *manifest.get("outputs", [])]:
        path = Path(item["path"])
        if not path.exists() or _sha256(path) != item["sha256"]:
            raise ValueError(f"invalid manifested file {path}")
        if "rows" in item and len(_read_csv(path)) != int(item["rows"]):
            raise ValueError(f"row count mismatch for manifested file {path}")
        paths[path.name] = path
    return manifest, paths


def verify_literature(
    *,
    contract: dict[str, Any],
    inventory: list[dict[str, str]],
    related_work_text: str,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    policy = contract["literature_verification"]
    if len(inventory) != policy["expected_unique_sources"]:
        raise ValueError("H7C related-work inventory has an unexpected source count")
    if len({row["source_key"] for row in inventory}) != len(inventory):
        raise ValueError("H7C related-work source keys must be unique")
    occurrences = sum(int(row["prior_occurrences"]) for row in inventory)
    if occurrences != policy["expected_prior_occurrences"]:
        raise ValueError("H7C prior daftar occurrence count changed")
    accepted = set(policy["accepted_evidence_authorities"])
    verified: list[dict[str, str]] = []
    for row in inventory:
        if row["verification_level"] != policy["required_final_status"]:
            raise ValueError(f"source {row['source_key']} is not metadata-verified")
        if row["evidence_authority"] not in accepted:
            raise ValueError(f"source {row['source_key']} has an unsupported authority")
        if not row["evidence_url"].startswith("https://"):
            raise ValueError(f"source {row['source_key']} lacks an HTTPS primary URL")
        if row["evidence_url"] not in related_work_text:
            raise ValueError(f"source {row['source_key']} is not linked in related-work")
        if not row["identifier"] or not row["canonical_year"].isdigit():
            raise ValueError(f"source {row['source_key']} lacks canonical metadata")
        verified.append({**row, "verification_result": "verified_primary_metadata"})
    remaining = related_work_text.count(policy["unverified_marker"])
    if remaining:
        raise ValueError(f"related-work retains {remaining} daftar table rows")
    verified.sort(key=lambda row: row["source_key"])
    return verified, {
        "unique_sources": len(verified),
        "prior_occurrences": occurrences,
        "remaining_daftar": remaining,
    }


def verify_components(
    *,
    contract: dict[str, Any],
    decisions: list[dict[str, str]],
    compose_text: str,
    pyproject_text: str,
) -> list[dict[str, str]]:
    policy = contract["optional_components"]
    expected = policy["expected_components"]
    if [row["component"] for row in decisions] != expected:
        raise ValueError("H7C optional component inventory is incomplete or reordered")
    if any(row["status"] != policy["required_current_status"] for row in decisions):
        raise ValueError("an optional component is reported active without an H7C contract change")
    compose_lower = compose_text.lower()
    forbidden_services = ["\n  trino:", "\n  openmetadata:", "\n  airflow:"]
    if any(service in compose_lower for service in forbidden_services):
        raise ValueError("component decision conflicts with docker-compose services")
    if "geopandas" in pyproject_text.lower():
        raise ValueError("component decision conflicts with Python dependencies")
    return decisions


def extend_treatment_lineage(
    *,
    contract: dict[str, Any],
    base_nodes: list[dict[str, str]],
    base_edges: list[dict[str, str]],
    base_paths: list[dict[str, str]],
    treatment_inputs: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    nodes = {
        row["node_id"]: {**row, "treatment_id": "", "observation_id": "", "decision": "", "addressable": ""}
        for row in base_nodes
    }
    edges = {row["edge_id"]: {**row, "treatment_id": ""} for row in base_edges}
    if len(nodes) != len(base_nodes) or len(edges) != len(base_edges):
        raise ValueError("H7C base H6C graph identities are not unique")
    observation_nodes = {
        row["natural_key"]: row["node_id"]
        for row in base_nodes
        if row["node_type"] == "observation"
    }
    cell_nodes = {
        row["natural_key"]: row["node_id"]
        for row in base_nodes
        if row["node_type"] == "indicator_cell"
    }
    domains = {
        row["natural_key"]: row["domain"]
        for row in base_nodes
        if row["node_type"] == "observation"
    }
    source_paths = {row["observation_id"]: row for row in base_paths}
    lineage_rows: list[dict[str, str]] = []

    def add_node(row: dict[str, str]) -> None:
        existing = nodes.get(row["node_id"])
        if existing is not None and existing != row:
            raise ValueError(f"conflicting H7C node {row['node_id']}")
        nodes[row["node_id"]] = row

    def add_edge(
        relationship: str,
        from_node_id: str,
        to_node_id: str,
        *,
        treatment_id: str,
        observation_id: str,
        cell_id: str,
        evidence_basis: str,
    ) -> None:
        edge_id = f"edge:{_id(relationship, from_node_id, to_node_id)}"
        row = {
            "edge_id": edge_id,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "relationship": relationship,
            "observation_id": observation_id,
            "cell_id": cell_id,
            "evidence_basis": evidence_basis,
            "treatment_id": treatment_id,
        }
        existing = edges.get(edge_id)
        if existing is not None and existing != row:
            raise ValueError(f"conflicting H7C edge {edge_id}")
        edges[edge_id] = row

    for item in treatment_inputs:
        treatment_id = item["treatment_id"]
        rows = item["rows"]
        manifest_path = item["manifest_path"]
        manifest_sha = item["manifest_sha256"]
        if len(rows) != contract["lineage_extension"]["required_decisions_per_treatment"]:
            raise ValueError(f"{treatment_id} does not cover the frozen H6 workload")
        run_node_id = _node_id("treatment_run", treatment_id, manifest_sha)
        add_node(
            {
                "node_id": run_node_id,
                "node_type": "treatment_run",
                "natural_key": f"{treatment_id}|{manifest_sha}",
                "label": f"{treatment_id} treatment run",
                "domain": "",
                "source_id": "",
                "vintage_id": "",
                "path": manifest_path,
                "sha256": manifest_sha,
                "treatment_id": treatment_id,
                "observation_id": "",
                "decision": "",
                "addressable": "",
            }
        )
        output_nodes_for_treatment: set[str] = set()
        for row in sorted(rows, key=lambda value: value["requested_observation_id"]):
            requested = row["requested_observation_id"]
            cell_id = row["cell_id"]
            available = row[item["available_column"]]
            decision = row["result"]
            output_observation = row[item["output_column"]]
            if requested not in observation_nodes or requested not in source_paths:
                raise ValueError(f"{treatment_id} decision lacks exact H6C source lineage")
            if cell_id not in cell_nodes or source_paths[requested]["cell_id"] != cell_id:
                raise ValueError(f"{treatment_id} decision points to the wrong stable cell")
            if available not in {"yes", "no"} or not output_observation:
                raise ValueError(f"{treatment_id} decision has invalid addressability")
            observation_node_id = observation_nodes[requested]
            decision_node_id = _node_id("treatment_decision", treatment_id, requested)
            output_node_id = _node_id(
                "treatment_output", treatment_id, cell_id, output_observation
            )
            output_nodes_for_treatment.add(output_node_id)
            add_node(
                {
                    "node_id": decision_node_id,
                    "node_type": "treatment_decision",
                    "natural_key": f"{treatment_id}|{requested}",
                    "label": f"{treatment_id}:{decision}",
                    "domain": domains[requested],
                    "source_id": "",
                    "vintage_id": "",
                    "path": "",
                    "sha256": "",
                    "treatment_id": treatment_id,
                    "observation_id": requested,
                    "decision": decision,
                    "addressable": available,
                }
            )
            add_node(
                {
                    "node_id": output_node_id,
                    "node_type": "treatment_output",
                    "natural_key": f"{treatment_id}|{cell_id}|{output_observation}",
                    "label": f"{treatment_id}:{cell_id}",
                    "domain": domains[requested],
                    "source_id": "",
                    "vintage_id": "",
                    "path": "",
                    "sha256": "",
                    "treatment_id": treatment_id,
                    "observation_id": output_observation,
                    "decision": "serving_output",
                    "addressable": "yes",
                }
            )
            add_edge(
                "observation_enters_treatment",
                observation_node_id,
                decision_node_id,
                treatment_id=treatment_id,
                observation_id=requested,
                cell_id=cell_id,
                evidence_basis="exact H6 observation_id carried by the treatment audit",
            )
            add_edge(
                "treatment_run_evaluates_candidate",
                run_node_id,
                decision_node_id,
                treatment_id=treatment_id,
                observation_id=requested,
                cell_id=cell_id,
                evidence_basis="checksummed H7 treatment manifest and audit row",
            )
            add_edge(
                "decision_resolves_to_output",
                decision_node_id,
                output_node_id,
                treatment_id=treatment_id,
                observation_id=requested,
                cell_id=cell_id,
                evidence_basis="exact current or selected observation_id in the treatment audit",
            )
            add_edge(
                "output_serves_cell",
                output_node_id,
                cell_nodes[cell_id],
                treatment_id=treatment_id,
                observation_id=output_observation,
                cell_id=cell_id,
                evidence_basis="treatment output and H6C cell share the exact stable cell_id",
            )
            source_path = source_paths[requested]
            lineage_rows.append(
                {
                    "treatment_lineage_id": f"treatment_path:{_id(treatment_id, requested)}",
                    "treatment_id": treatment_id,
                    "cell_id": cell_id,
                    "requested_observation_id": requested,
                    "source_lineage_path_id": source_path["lineage_path_id"],
                    "source_record_node_id": source_path["source_record_node_id"],
                    "observation_node_id": observation_node_id,
                    "treatment_run_node_id": run_node_id,
                    "treatment_decision_node_id": decision_node_id,
                    "treatment_output_node_id": output_node_id,
                    "output_observation_id": output_observation,
                    "decision": decision,
                    "requested_addressable": available,
                    "treatment_manifest_path": manifest_path,
                    "treatment_manifest_sha256": manifest_sha,
                    "complete": "yes",
                }
            )
        if len(output_nodes_for_treatment) != contract["lineage_extension"]["required_outputs_per_treatment"]:
            raise ValueError(f"{treatment_id} output lineage does not contain 14 stable cells")

    node_rows = sorted(nodes.values(), key=lambda row: (row["node_type"], row["node_id"]))
    edge_rows = sorted(edges.values(), key=lambda row: (row["relationship"], row["edge_id"]))
    lineage_rows.sort(key=lambda row: (row["treatment_id"], row["cell_id"], row["requested_observation_id"]))
    known_nodes = set(nodes)
    if any(row["from_node_id"] not in known_nodes or row["to_node_id"] not in known_nodes for row in edge_rows):
        raise ValueError("H7C edge references an unknown node")
    if any(row["complete"] != "yes" for row in lineage_rows):
        raise ValueError("H7C treatment lineage is incomplete")
    metrics = {
        "base_nodes": len(base_nodes),
        "base_edges": len(base_edges),
        "combined_nodes": len(node_rows),
        "combined_edges": len(edge_rows),
        "treatment_paths": len(lineage_rows),
        "addressable_requests": sum(row["requested_addressable"] == "yes" for row in lineage_rows),
        "non_addressable_requests": sum(row["requested_addressable"] == "no" for row in lineage_rows),
        "treatment_outputs": sum(row["node_type"] == "treatment_output" for row in node_rows),
    }
    return node_rows, edge_rows, lineage_rows, metrics


def run_h7c(
    *,
    contract_path: Path,
    literature_inventory_path: Path,
    component_decisions_path: Path,
    related_work_path: Path,
    compose_path: Path,
    pyproject_path: Path,
    h6c_manifest_path: Path,
    h7_manifest_path: Path,
    h7b_manifest_path: Path,
    nodes_output: Path,
    edges_output: Path,
    treatment_lineage_output: Path,
    literature_output: Path,
    components_output: Path,
    validation_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    related_text = related_work_path.read_text(encoding="utf-8")
    literature_rows, literature_metrics = verify_literature(
        contract=contract,
        inventory=_read_csv(literature_inventory_path),
        related_work_text=related_text,
    )
    component_rows = verify_components(
        contract=contract,
        decisions=_read_csv(component_decisions_path),
        compose_text=compose_path.read_text(encoding="utf-8"),
        pyproject_text=pyproject_path.read_text(encoding="utf-8"),
    )

    h6c_manifest, h6c_paths = _verified_manifest(
        h6c_manifest_path, expected_stage="H6", expected_track="C"
    )
    if h6c_manifest.get("lineage_status") != "validated" or h6c_manifest.get("contract_version") != "h6c.1":
        raise ValueError("H7C requires the validated H6C graph")
    h7_manifest, h7_paths = _verified_manifest(
        h7_manifest_path, expected_stage="H7", expected_treatment="B0"
    )
    h7b_manifest, h7b_paths = _verified_manifest(
        h7b_manifest_path, expected_stage="H7", expected_track="B", expected_treatment="B2"
    )
    required_h6c = {
        "h6c-lineage-nodes.csv",
        "h6c-lineage-edges.csv",
        "h6c-cell-source-paths.csv",
    }
    if missing := required_h6c - h6c_paths.keys():
        raise ValueError(f"H6C manifest lacks {sorted(missing)}")
    if "h7-b0-reproducibility.csv" not in h7_paths or "h7b-b2-reproducibility.csv" not in h7b_paths:
        raise ValueError("H7C requires both treatment reproducibility audits")

    base_nodes = _read_csv(h6c_paths["h6c-lineage-nodes.csv"])
    base_edges = _read_csv(h6c_paths["h6c-lineage-edges.csv"])
    base_paths = _read_csv(h6c_paths["h6c-cell-source-paths.csv"])
    nodes, edges, treatment_lineage, lineage_metrics = extend_treatment_lineage(
        contract=contract,
        base_nodes=base_nodes,
        base_edges=base_edges,
        base_paths=base_paths,
        treatment_inputs=[
            {
                "treatment_id": "B0",
                "rows": _read_csv(h7_paths["h7-b0-reproducibility.csv"]),
                "available_column": "available_by_vintage",
                "output_column": "current_observation_id",
                "manifest_path": str(h7_manifest_path),
                "manifest_sha256": _sha256(h7_manifest_path),
            },
            {
                "treatment_id": "B2",
                "rows": _read_csv(h7b_paths["h7b-b2-reproducibility.csv"]),
                "available_column": "available_by_observation_id",
                "output_column": "selected_observation_id",
                "manifest_path": str(h7b_manifest_path),
                "manifest_sha256": _sha256(h7b_manifest_path),
            },
        ],
    )
    completeness = sum(row["complete"] == "yes" for row in treatment_lineage) / len(treatment_lineage)
    per_treatment = Counter(row["treatment_id"] for row in treatment_lineage)
    validation = [
        {"invariant": "h7c_contract", "status": "passed", "checked_rows": "7", "detail": "literature, lineage extension, component, and exact-matching policies match h7c.1"},
        {"invariant": "prior_daftar_inventory", "status": "passed", "checked_rows": str(literature_metrics["prior_occurrences"]), "detail": f"{literature_metrics['unique_sources']} unique records account for every prior daftar occurrence"},
        {"invariant": "primary_metadata_evidence", "status": "passed", "checked_rows": str(literature_metrics["unique_sources"]), "detail": "every source has an HTTPS publisher, repository, institution, product, or project record"},
        {"invariant": "no_remaining_daftar", "status": "passed", "checked_rows": str(literature_metrics["remaining_daftar"]), "detail": "related-work contains no unverified table row"},
        {"invariant": "base_h6c_graph_immutable", "status": "passed", "checked_rows": str(len(base_nodes) + len(base_edges)), "detail": "all H6C node and edge rows are copied without identity changes"},
        {"invariant": "treatment_decision_coverage", "status": "passed", "checked_rows": str(lineage_metrics["treatment_paths"]), "detail": f"B0={per_treatment['B0']} and B2={per_treatment['B2']} decisions cover the same H6 workload"},
        {"invariant": "source_to_output_paths", "status": "passed", "checked_rows": str(lineage_metrics["treatment_paths"]), "detail": "every treatment decision inherits one exact H6C source path and resolves to one serving output"},
        {"invariant": "optional_components_disclosed", "status": "passed", "checked_rows": str(len(component_rows)), "detail": "Trino, OpenMetadata, Airflow, and GeoPandas are explicitly not used"},
        {"invariant": "no_fuzzy_matching", "status": "passed", "checked_rows": str(lineage_metrics["combined_edges"]), "detail": "all inherited and new edges use hashes, manifests, observation_id, or cell_id"},
    ]

    written_outputs = []
    for path, columns, rows in (
        (nodes_output, NODE_COLUMNS, nodes),
        (edges_output, EDGE_COLUMNS, edges),
        (treatment_lineage_output, TREATMENT_LINEAGE_COLUMNS, treatment_lineage),
        (literature_output, LITERATURE_COLUMNS, literature_rows),
        (components_output, COMPONENT_COLUMNS, component_rows),
        (validation_output, VALIDATION_COLUMNS, validation),
    ):
        written_outputs.append(
            {"path": str(path), "rows": len(rows), "sha256": _write_csv(path, columns, rows)}
        )

    manifest = {
        "stage": "H7",
        "track": "C",
        "contract_version": contract["contract_version"],
        "evidence_status": "validated",
        "literature": literature_metrics,
        "lineage": {
            **lineage_metrics,
            "completeness_rate": f"{completeness:.4f}",
            "matching": contract["lineage_extension"]["matching"],
        },
        "optional_components": {
            "assessed": len(component_rows),
            "used": 0,
            "not_used": len(component_rows),
        },
        "inputs": [
            {"path": str(path), "sha256": _sha256(path)}
            for path in (
                contract_path,
                literature_inventory_path,
                component_decisions_path,
                related_work_path,
                compose_path,
                pyproject_path,
                h6c_manifest_path,
                h7_manifest_path,
                h7b_manifest_path,
            )
        ],
        "outputs": written_outputs,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        **literature_metrics,
        **lineage_metrics,
        "completeness_rate": f"{completeness:.4f}",
        "optional_components_not_used": len(component_rows),
        "status": "validated",
    }
