from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .inventory import indicator_paths, load_indicators


API_ENDPOINT = "https://webapi.bps.go.id/v1/api/list/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
)
STOPWORDS = {
    "atau",
    "dan",
    "dengan",
    "dari",
    "ke",
    "menurut",
    "pada",
    "per",
    "persentase",
    "proporsi",
    "rata",
    "rumah",
    "tangga",
    "yang",
}
CANDIDATE_COLUMNS = [
    "indicator_key",
    "domain",
    "indicator_name",
    "rank",
    "match_score",
    "webapi_domain_id",
    "webapi_variable_id",
    "webapi_title",
    "subject_id",
    "subject_name",
]
FREE_SELECTION_STATUSES = {"selected", "selected_limited", "selected_derived"}
FREE_PUBLICATIONS = [
    {
        "source_id": "bps_tpb_2025",
        "year": "2025",
        "publication_id": "8ffdc46aa817bf0c4c47e105",
    },
    {
        "source_id": "bps_tpb_2024",
        "year": "2024",
        "publication_id": "936a26d5d2b168b9971d3b02",
    },
]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"").strip("'"))


def _request_api(api_key: str, parameters: dict[str, str], label: str) -> dict[str, Any]:
    query = urlencode({**parameters, "key": api_key}, safe=";:")
    request = Request(
        f"{API_ENDPOINT}?{query}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://webapi.bps.go.id/documentation/",
        },
    )
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise RuntimeError(f"BPS returned an empty or invalid payload for {label}")
            if payload.get("status") != "OK":
                message = payload.get("message", "no message")
                raise RuntimeError(
                    f"BPS returned status {payload.get('status')!r} for {label}: {message}"
                )
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
            last_error = error
            if attempt < 5:
                time.sleep(min(8, 2**attempt))
    raise RuntimeError(f"BPS WebAPI request failed for {label}: {last_error}")


def _request_page(api_key: str, domain: str, page: int) -> dict[str, Any]:
    return _request_api(
        api_key,
        {
            "model": "var",
            "lang": "ind",
            "domain": domain,
            "area": "1",
            "page": str(page),
        },
        f"variable catalog page {page}",
    )


def _normalise(value: str) -> str:
    value = value.lower().replace("pdb/pdrb", "pdb pdrb")
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _score(query: str, title: str) -> float:
    query_normal = _normalise(query)
    title_normal = _normalise(title)
    query_tokens = {token for token in query_normal.split() if token not in STOPWORDS}
    title_tokens = {token for token in title_normal.split() if token not in STOPWORDS}
    coverage = len(query_tokens & title_tokens) / max(1, len(query_tokens))
    sequence = SequenceMatcher(None, query_normal, title_normal).ratio()
    return round((0.7 * coverage) + (0.3 * sequence), 4)


def _write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def _download_bytes(url: str, label: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,*/*",
            "Referer": "https://www.bps.go.id/",
        },
    )
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=180) as response:
                content = response.read()
            if not content.startswith(b"%PDF"):
                raise RuntimeError(f"BPS did not return a PDF for {label}")
            return content
        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            last_error = error
            if attempt < 3:
                time.sleep(min(8, 2**attempt))
    raise RuntimeError(f"BPS publication download failed for {label}: {last_error}")


def fetch_free_publications(
    *,
    env_file: Path,
    raw_dir: Path,
    manifest_output: Path,
) -> dict[str, int]:
    _load_env_file(env_file)
    api_key = os.environ.get("BPS_API_KEY", "").strip()
    if not api_key:
        raise ValueError(f"BPS_API_KEY is empty; populate {env_file}")

    retrieved_at = datetime.now(timezone.utc).isoformat()
    files: list[dict[str, Any]] = []
    for spec in FREE_PUBLICATIONS:
        parameters = {
            "model": "publication",
            "lang": "ind",
            "domain": "0000",
            "page": "1",
            "year": spec["year"],
            "keyword": "Tujuan Pembangunan Berkelanjutan",
        }
        first = _request_api(
            api_key, parameters, f"publication catalog {spec['year']}, page 1"
        )
        page_count = int(first["data"][0]["pages"])
        rows = list(first["data"][1])
        for page in range(2, page_count + 1):
            payload = _request_api(
                api_key,
                {**parameters, "page": str(page)},
                f"publication catalog {spec['year']}, page {page}",
            )
            rows.extend(payload["data"][1])
        publication = next(
            (row for row in rows if row["pub_id"] == spec["publication_id"]), None
        )
        if publication is None:
            raise RuntimeError(f"Publication {spec['publication_id']} was not found")

        content = _download_bytes(publication["pdf"], publication["title"])
        raw_path = raw_dir / f"{spec['source_id']}.pdf"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(content)
        files.append(
            {
                "source_id": spec["source_id"],
                "publication_id": spec["publication_id"],
                "title": publication["title"],
                "release_date": publication.get("rl_date", ""),
                "update_date": publication.get("updt_date", ""),
                "raw_path": str(raw_path),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "download_url": publication["pdf"],
            }
        )

    manifest = {
        "retrieved_at": retrieved_at,
        "channel": "BPS WebAPI publication catalog",
        "cost_class": "free",
        "authentication": "BPS_API_KEY environment variable",
        "key_fingerprint": hashlib.sha256(api_key.encode()).hexdigest()[:8],
        "files": files,
    }
    _write_json(manifest_output, manifest)
    return {"publication_count": len(files), "byte_count": sum(item["bytes"] for item in files)}


def discover_webapi_variables(
    *,
    domain: str,
    indicator_dir: Path,
    env_file: Path,
    raw_output: Path,
    candidate_output: Path,
    manifest_output: Path,
    workers: int,
    top: int,
) -> dict[str, int]:
    _load_env_file(env_file)
    api_key = os.environ.get("BPS_API_KEY", "").strip()
    if not api_key:
        raise ValueError(f"BPS_API_KEY is empty; populate {env_file}")
    if workers < 1 or top < 1:
        raise ValueError("workers and top must be positive")

    retrieved_at = datetime.now(timezone.utc).isoformat()
    first = _request_page(api_key, domain, 1)
    page_info = first["data"][0]
    page_count = int(page_info["pages"])
    pages: dict[int, dict[str, Any]] = {1: first}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_request_page, api_key, domain, page): page
            for page in range(2, page_count + 1)
        }
        for future in as_completed(futures):
            page = futures[future]
            pages[page] = future.result()

    variables: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        variables.extend(pages[page]["data"][1])
    variables.sort(key=lambda row: int(row["var_id"]))

    catalog = {
        "source_id": "bps_webapi",
        "retrieved_at": retrieved_at,
        "domain": domain,
        "model": "var",
        "page_count": page_count,
        "variable_count": len(variables),
        "variables": variables,
    }
    checksum = _write_json(raw_output, catalog)

    indicators = load_indicators(indicator_paths(indicator_dir))
    candidates: list[dict[str, str]] = []
    for indicator in indicators:
        ranked = sorted(
            ((_score(indicator["indicator_name"], item["title"]), item) for item in variables),
            key=lambda pair: (-pair[0], int(pair[1]["var_id"])),
        )[:top]
        for rank, (score, item) in enumerate(ranked, start=1):
            candidates.append(
                {
                    "indicator_key": indicator["indicator_key"],
                    "domain": indicator["domain"],
                    "indicator_name": indicator["indicator_name"],
                    "rank": str(rank),
                    "match_score": f"{score:.4f}",
                    "webapi_domain_id": domain,
                    "webapi_variable_id": str(item["var_id"]),
                    "webapi_title": item["title"],
                    "subject_id": str(item["sub_id"]),
                    "subject_name": item["sub_name"],
                }
            )

    candidate_output.parent.mkdir(parents=True, exist_ok=True)
    with candidate_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)

    manifest = {
        "source_id": "bps_webapi",
        "retrieved_at": retrieved_at,
        "request": {
            "endpoint": API_ENDPOINT,
            "model": "var",
            "domain": domain,
            "area": 1,
            "authentication": "BPS_API_KEY environment variable",
        },
        "raw_path": str(raw_output),
        "sha256": checksum,
        "page_count": page_count,
        "record_count": len(variables),
        "key_fingerprint": hashlib.sha256(api_key.encode()).hexdigest()[:8],
    }
    _write_json(manifest_output, manifest)
    return {"variable_count": len(variables), "candidate_count": len(candidates)}


def _read_free_selection(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            variable_id = row["webapi_variable_id"].strip()
            if row["selection_status"] not in FREE_SELECTION_STATUSES or not variable_id:
                continue
            key = (row["webapi_domain_id"], variable_id)
            item = selected.setdefault(
                key,
                {
                    "domain": row["webapi_domain_id"],
                    "variable_id": variable_id,
                    "indicator_keys": [],
                    "selection_statuses": [],
                    "coverage": [],
                    "producer": row["producer"],
                },
            )
            item["indicator_keys"].append(row["indicator_key"])
            item["selection_statuses"].append(row["selection_status"])
            item["coverage"].append(row["coverage"])
    return selected


def _all_periods(api_key: str, domain: str, variable_id: str) -> list[dict[str, Any]]:
    parameters = {
        "model": "th",
        "lang": "ind",
        "domain": domain,
        "var": variable_id,
        "page": "1",
    }
    first = _request_api(api_key, parameters, f"periods for variable {variable_id}, page 1")
    page_count = int(first["data"][0]["pages"])
    pages = {1: first}
    for page in range(2, page_count + 1):
        pages[page] = _request_api(
            api_key,
            {**parameters, "page": str(page)},
            f"periods for variable {variable_id}, page {page}",
        )
    periods: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        periods.extend(pages[page]["data"][1])
    return periods


def _period_year(period: dict[str, Any]) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", str(period.get("th", "")))
    return int(match.group()) if match else None


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[start : start + size] for start in range(0, len(values), size)]


def _fetch_selected_variable(
    *,
    api_key: str,
    selection: dict[str, Any],
    raw_dir: Path,
    since_year: int,
    retrieved_at: str,
) -> dict[str, Any]:
    domain = selection["domain"]
    variable_id = selection["variable_id"]
    all_periods = _all_periods(api_key, domain, variable_id)
    periods = [
        period
        for period in all_periods
        if (year := _period_year(period)) is not None and year >= since_year
    ]
    period_ids = [str(period["th_id"]) for period in periods]
    responses: list[dict[str, Any]] = []
    for batch in _chunks(period_ids, 3):
        responses.append(
            _request_api(
                api_key,
                {
                    "model": "data",
                    "lang": "ind",
                    "domain": domain,
                    "var": variable_id,
                    "th": ";".join(batch),
                },
                f"data for variable {variable_id}, periods {';'.join(batch)}",
            )
        )

    raw_path = raw_dir / f"var-{domain}-{variable_id}.json"
    payload = {
        "source_id": "bps_webapi",
        "retrieved_at": retrieved_at,
        "request": {
            "endpoint": API_ENDPOINT,
            "domain": domain,
            "variable_id": variable_id,
            "since_year": since_year,
            "maximum_periods_per_request": 3,
        },
        "selection": selection,
        "available_periods": all_periods,
        "selected_periods": periods,
        "responses": responses,
    }
    checksum = _write_json(raw_path, payload)
    cell_count = sum(len(response.get("datacontent", {})) for response in responses)
    title = ""
    for response in responses:
        if response.get("var"):
            title = str(response["var"][0].get("label", ""))
            break
    return {
        "domain": domain,
        "variable_id": variable_id,
        "title": title,
        "indicator_keys": sorted(set(selection["indicator_keys"])),
        "selection_statuses": sorted(set(selection["selection_statuses"])),
        "raw_path": str(raw_path),
        "sha256": checksum,
        "available_period_count": len(all_periods),
        "selected_period_count": len(periods),
        "selected_period_labels": [str(period["th"]) for period in periods],
        "data_cell_count": cell_count,
    }


def fetch_free_webapi_data(
    *,
    selection_path: Path,
    env_file: Path,
    raw_dir: Path,
    manifest_output: Path,
    workers: int,
    since_year: int,
) -> dict[str, int]:
    _load_env_file(env_file)
    api_key = os.environ.get("BPS_API_KEY", "").strip()
    if not api_key:
        raise ValueError(f"BPS_API_KEY is empty; populate {env_file}")
    if workers < 1:
        raise ValueError("workers must be positive")

    selections = _read_free_selection(selection_path)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    files: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _fetch_selected_variable,
                api_key=api_key,
                selection=selection,
                raw_dir=raw_dir,
                since_year=since_year,
                retrieved_at=retrieved_at,
            ): key
            for key, selection in selections.items()
        }
        for future in as_completed(futures):
            files.append(future.result())
    files.sort(key=lambda item: (item["domain"], int(item["variable_id"])))

    manifest = {
        "source_id": "bps_webapi",
        "retrieved_at": retrieved_at,
        "selection_path": str(selection_path),
        "policy": {
            "cost_class": "free",
            "since_year": since_year,
            "excluded_sources": ["bps_dna", "bps_sirusa", "silastik_pst", "paid_digital_maps"],
        },
        "authentication": "BPS_API_KEY environment variable",
        "key_fingerprint": hashlib.sha256(api_key.encode()).hexdigest()[:8],
        "file_count": len(files),
        "files": files,
    }
    _write_json(manifest_output, manifest)
    return {
        "variable_count": len(files),
        "period_count": sum(item["selected_period_count"] for item in files),
        "cell_count": sum(item["data_cell_count"] for item in files),
    }
