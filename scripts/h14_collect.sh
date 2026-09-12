#!/usr/bin/env bash
# H14: collect the query plan, the session log and the bytes every treatment statement
# reads. The statements are the frozen H11 injection statements, unchanged; only the
# instrumentation is new, and the seconds of this run are deliberately not reported.
#
# Run this on the stack host with a clean working tree and a persistent catalog.
set -euo pipefail

project_dir="${1:-.}"
run_label="${2:?usage: h14_collect.sh PROJECT_DIR RUN_LABEL}"
cd "$project_dir"
# shellcheck source=scripts/h11_sql.sh
source scripts/h11_sql.sh

contract="contracts/h14-plan-and-read-statistics.json"
raw_dir="results/raw/h14/${run_label}"
if [[ -e "$raw_dir" ]]; then
  echo "raw run directory ${raw_dir} already exists; measurements are never overwritten" >&2
  exit 1
fi
h11_load_manifest
git_dirty="$(git status --porcelain | wc -l | tr -d ' ')"

read -r repetitions < <(python3 -c '
import json
print(json.load(open("'"$contract"'"))["protocol"]["repetitions"])
')
scenarios=()
while read -r scenario; do
  scenarios+=("$scenario")
done < <(python3 -c '
import json
for scenario in json.load(open("'"$contract"'"))["workload"]["scenarios"]:
    print(scenario)
')

compose=(docker compose --env-file infra/docker/versions.env)
container_raw="/home/iceberg/${raw_dir}"

mkdir -p "$raw_dir/plans" "$raw_dir/logs" "$raw_dir/eventlogs"
{
  echo "run_label=${run_label}"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_dirty_entries=${git_dirty}"
  echo "git_dirty_paths=$(git status --porcelain | awk '{print $2}' | head -10 | paste -sd';' -)"
  echo "hostname=$(hostname)"
  echo "host_nproc=$(nproc)"
  echo "spark_driver_memory=$("${compose[@]}" exec -T spark printenv SPARK_DRIVER_MEMORY </dev/null | tr -d '\r')"
  echo "spark_defaults_sha256=$(sha256sum infra/spark/spark-defaults.conf | cut -d' ' -f1)"
  echo "payload_manifest_sha256=$(sha256sum data/manifests/h11-main-sweep-payload.json | cut -d' ' -f1)"
  echo "repetitions=${repetitions}"
  echo "scenarios=$(IFS=';'; echo "${scenarios[*]}")"
  echo "instrumentation=event_log_enabled;timings_not_reported"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$raw_dir/environment.txt"

# One instrumented session per treatment. The plan is captured first, then the same
# statements run for real so the scan metrics belong to the statement that was explained.
run_instrumented() {
  local rep="$1" scenario="$2" treatment="$3" write_sql="$4" maintenance_sql="$5"
  local tag="rep${rep}-${scenario}-${treatment}"
  local eventlog="${raw_dir}/eventlogs/${tag}"
  mkdir -p "$eventlog"
  local sql="$(h11_views "$scenario")
EXPLAIN FORMATTED ${write_sql%;}
;
${write_sql}
${maintenance_sql}"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql \
    --conf spark.eventLog.enabled=true \
    --conf "spark.eventLog.dir=file:${container_raw}/eventlogs/${tag}" \
    --conf spark.sql.debug.maxToStringFields=200 \
    -e "$sql" </dev/null 2>&1)"
  local status=$?
  set -e
  printf '%s\n' "$output" > "${raw_dir}/logs/${tag}.log"
  if (( status != 0 )); then
    echo "H14 ${treatment} failed in ${tag} with status ${status}; see the log" >&2
    exit "$status"
  fi
  # The plan is everything the explain printed before the first executed statement.
  printf '%s\n' "$output" | sed -n '/^== Physical Plan ==/,/^Time taken/p' | sed '$d' \
    > "${raw_dir}/plans/${tag}.plan"
  if [[ ! -s "${raw_dir}/plans/${tag}.plan" ]]; then
    echo "H14 captured no plan for ${tag}" >&2
    exit 1
  fi
}

# Iceberg reports its scan metrics as driver accumulator updates, and the staging CSV
# views report theirs as task input metrics, so both have to be read out of the event log.
parse_event_log() {
  local rep="$1" scenario="$2" treatment="$3"
  local tag="rep${rep}-${scenario}-${treatment}"
  "${compose[@]}" exec -T spark python3 -c '
import json
import os
import sys

rep, scenario, treatment, directory = sys.argv[1:5]
wanted = {
    "total data file size (bytes)": "iceberg_bytes_read",
    "total delete file size (bytes)": "delete_bytes_read",
    "number of result data files": "data_files_read",
    "number of skipped data files": "data_files_skipped",
    "number of output rows": "output_rows",
}
for name in sorted(os.listdir(directory)):
    path = os.path.join(directory, name)
    if name.endswith(".gz"):
        continue
    accumulators = {}
    descriptions = {}
    stage_execution = {}
    totals = {}

    def add(execution, metric, value):
        totals.setdefault(execution, {}).setdefault(metric, 0)
        totals[execution][metric] += int(value)

    def walk(node, execution):
        for metric in node.get("metrics", []):
            if metric["name"] in wanted:
                accumulators[metric["accumulatorId"]] = (execution, wanted[metric["name"]])
        for child in node.get("children", []):
            walk(child, execution)

    for line in open(path):
        event = json.loads(line)
        kind = event["Event"]
        if kind.endswith("SparkListenerSQLExecutionStart"):
            execution = str(event["executionId"])
            text = (event.get("description") or "").strip().split("\n")
            descriptions[execution] = " ".join(part.strip() for part in text[:2])[:140]
            walk(event.get("sparkPlanInfo", {}), execution)
        elif kind.endswith("SparkListenerSQLAdaptiveExecutionUpdate"):
            walk(event.get("sparkPlanInfo", {}), str(event["executionId"]))
        elif kind.endswith("SparkListenerDriverAccumUpdates"):
            for accumulator, value in event.get("accumUpdates", []):
                if accumulator in accumulators:
                    execution, metric = accumulators[accumulator]
                    add(execution, metric, value)
        elif kind == "SparkListenerJobStart":
            execution = (event.get("Properties") or {}).get("spark.sql.execution.id")
            if execution is not None:
                for stage in event.get("Stage IDs", []):
                    stage_execution[stage] = str(execution)
        elif kind == "SparkListenerTaskEnd":
            execution = stage_execution.get(event.get("Stage ID"))
            if execution is not None:
                metrics = event.get("Task Metrics", {}).get("Input Metrics", {})
                if metrics.get("Bytes Read"):
                    add(execution, "file_bytes_read", metrics["Bytes Read"])
                if metrics.get("Records Read"):
                    add(execution, "file_records_read", metrics["Records Read"])
            for accumulator in event.get("Task Info", {}).get("Accumulables", []):
                if accumulator["ID"] in accumulators:
                    execution, metric = accumulators[accumulator["ID"]]
                    try:
                        update = int(accumulator.get("Update", 0))
                    except (TypeError, ValueError):
                        continue
                    add(execution, metric, update)
    for execution in sorted(totals, key=int):
        row = totals[execution]
        print(
            "|".join(
                [
                    "H14R",
                    rep,
                    scenario,
                    treatment,
                    execution,
                    str(row.get("iceberg_bytes_read", 0)),
                    str(row.get("file_bytes_read", 0)),
                    str(row.get("delete_bytes_read", 0)),
                    str(row.get("data_files_read", 0)),
                    str(row.get("data_files_skipped", 0)),
                    str(row.get("output_rows", 0)),
                    str(row.get("file_records_read", 0)),
                    descriptions.get(execution, ""),
                ]
            )
        )
' "$rep" "$scenario" "$treatment" "${container_raw}/eventlogs/${tag}" </dev/null \
    | grep -E '^H14R\|' >> "$raw_dir/read-statistics.txt"
  # The event log is the evidence for those numbers, so it is preserved, compressed.
  gzip -f "${raw_dir}/eventlogs/${tag}"/* 2>/dev/null || true
}

for rep in $(seq 1 "$repetitions"); do
  for scenario in "${scenarios[@]}"; do
    set +e
    baseline_output="$(bash scripts/h11_baseline.sh . 2>&1)"
    baseline_status=$?
    set -e
    if (( baseline_status != 0 )); then
      printf '%s\n' "$baseline_output" >&2
      echo "H14 baseline rebuild failed in repetition ${rep} ${scenario}" >&2
      exit "$baseline_status"
    fi
    printf '%s|%s|%s\n' "$rep" "$scenario" \
      "$(printf '%s\n' "$baseline_output" | grep -E '^H11B_VERIFY\|' | tail -1)" \
      >> "$raw_dir/baseline-markers.txt"

    run_instrumented "$rep" "$scenario" "B0" \
      "$(h11_b0_merge "$(h11_arrival_source "$((h11_arrivals + 1))")" "$((h11_arrivals + 1))")" \
      "$(h11_expire "$h11_b0_table")"
    parse_event_log "$rep" "$scenario" "B0"

    run_instrumented "$rep" "$scenario" "B1" "$(h11_b1_overwrite "$((h11_arrivals + 1))")" ""
    parse_event_log "$rep" "$scenario" "B1"

    run_instrumented "$rep" "$scenario" "B2" "$(h11_b2_overwrite)" "$(h11_expire "$h11_b2_table")"
    parse_event_log "$rep" "$scenario" "B2"

    run_instrumented "$rep" "$scenario" "B3" \
      "$(h11_b3_insert "$((h11_arrivals + 1))")
$(h11_b3_merge "stored.cell_id IN (SELECT DISTINCT cell_id FROM h11_dirty)" "$((h11_arrivals + 1))")" \
      "$(h11_expire "$h11_b3_store")
$(h11_expire "$h11_b3_serving")"
    parse_event_log "$rep" "$scenario" "B3"
  done
done

{
  echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$raw_dir/environment.txt"

echo "H14_RAW|${run_label}|${repetitions}|${#scenarios[@]}|$(ls "$raw_dir/plans" | wc -l)|$(ls "$raw_dir/logs" | wc -l)|$(grep -c '^H14R|' "$raw_dir/read-statistics.txt")"
