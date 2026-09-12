#!/usr/bin/env bash
# H11 baseline: rebuild the four treatments on the frozen province panel.
#
# The panel arrives release by release, and every treatment applies its own frozen
# write mechanism to each arrival, so the pre-revision state of a treatment is the
# state that treatment itself produces. Run this on the stack host.
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"
# shellcheck source=scripts/h11_sql.sh
source scripts/h11_sql.sh

h11_load_manifest
expectations="results/processed/h11-baseline-expectations.csv"

read -r expected_b0 expected_b1 expected_b2 expected_store expected_serving expected_b2_detail < <(python3 -c '
import csv

rows = {row["table"]: row for row in csv.DictReader(open("'"$expectations"'"))}
print(
    rows["kkciv.sweep.b0_panel_current"]["expected_rows"],
    rows["kkciv.sweep.b1_panel_full_snapshots"]["expected_rows"],
    rows["kkciv.sweep.b2_panel_selected"]["expected_rows"],
    rows["kkciv.sweep.b3_panel_observation_vintages"]["expected_rows"],
    rows["kkciv.sweep.b3_panel_current"]["expected_rows"],
    rows["kkciv.sweep.b2_panel_selected"]["detail"],
)
')

compose=(docker compose --env-file infra/docker/versions.env)

latest_panel_state() {
  cat <<'SQL'
  SELECT cell_id, observation_id FROM (
    SELECT cell_id, observation_id,
      row_number() OVER (PARTITION BY cell_id ORDER BY arrival_order DESC) AS resolution_rank
    FROM h11_panel
  ) resolved WHERE resolution_rank = 1
SQL
}

symmetric_diff() {
  local left="$1" right="$2"
  cat <<SQL
(SELECT count(*) FROM (
${left}
  EXCEPT
${right}
) left_only) + (SELECT count(*) FROM (
${right}
  EXCEPT
${left}
) right_only)
SQL
}

purge_sql=""
for table in "$h11_b0_table" "$h11_b1_table" "$h11_b2_table" "$h11_b3_store" "$h11_b3_serving"; do
  purge_sql+="DROP TABLE IF EXISTS ${table} PURGE;"
done

load_sql="$(h11_views)"
for arrival in $(seq 1 "$h11_arrivals"); do
  load_sql+="
$(h11_b0_merge "$(h11_arrival_source "$arrival")" "$arrival")"
done
load_sql+="
$(h11_expire "$h11_b0_table")"
for arrival in $(seq 1 "$h11_arrivals"); do
  load_sql+="
$(h11_b1_overwrite "$arrival")"
done
load_sql+="
$(h11_b2_overwrite)
$(h11_expire "$h11_b2_table")"
for arrival in $(seq 1 "$h11_arrivals"); do
  load_sql+="
$(h11_b3_insert "$arrival")
$(h11_b3_merge "stored.cell_id IN (SELECT DISTINCT cell_id FROM h11_edges_csv WHERE CAST(arrival_order AS INT) = ${arrival})" "$arrival")"
done
load_sql+="
$(h11_expire "$h11_b3_store")
$(h11_expire "$h11_b3_serving")
SELECT concat_ws('|', 'H11B_VERIFY',
  CAST((SELECT count(*) FROM ${h11_b0_table}) AS STRING),
  CAST((SELECT count(DISTINCT cell_id) FROM ${h11_b0_table}) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b1_table}) AS STRING),
  CAST((SELECT count(DISTINCT snapshot_order) FROM ${h11_b1_table}) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b2_table}) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b3_store}) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b3_serving}) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b0_table}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b1_table}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b2_table}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b3_store}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b3_serving}.snapshots) AS STRING),
  CAST($(symmetric_diff "  SELECT cell_id, observation_id FROM ${h11_b0_table}" "$(latest_panel_state)") AS STRING),
  CAST($(symmetric_diff "  SELECT cell_id, observation_id FROM ${h11_b1_table} WHERE snapshot_order = ${h11_arrivals}" "  SELECT cell_id, observation_id FROM ${h11_b0_table}") AS STRING),
  CAST($(symmetric_diff "  SELECT cell_id, observation_id FROM ${h11_b3_serving}" "  SELECT cell_id, observation_id FROM ${h11_b0_table}") AS STRING),
  (SELECT array_join(sort_array(collect_list(pair)), ';') FROM (
     SELECT concat(selected_source_id, '=', CAST(count(*) AS STRING)) AS pair
     FROM ${h11_b2_table} GROUP BY selected_source_id) pairs)
);"

# Purge, DDL and load run in one session: one JVM start per baseline rebuild.
session_sql="${purge_sql}
$(cat infra/spark/h11-sweep.sql)
${load_sql}"

set +e
output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$session_sql" </dev/null 2>&1)"
spark_status=$?
set -e
if (( spark_status != 0 )); then
  printf '%s\n' "$output" >&2
  echo "H11 baseline load failed with status ${spark_status}" >&2
  exit "$spark_status"
fi

marker="$(printf '%s\n' "$output" | grep -E '^H11B_VERIFY\|' | tail -1)"
if [[ -z "$marker" ]]; then
  printf '%s\n' "$output" >&2
  echo "H11 baseline produced no verification marker" >&2
  exit 1
fi
expected="H11B_VERIFY|${expected_b0}|${expected_b0}|${expected_b1}|${h11_arrivals}|${expected_b2}|${expected_store}|${expected_serving}|1|${h11_arrivals}|1|1|1|0|0|0|${expected_b2_detail}"
if [[ "$marker" != "$expected" ]]; then
  echo "H11 baseline marker mismatch" >&2
  echo "  expected ${expected}" >&2
  echo "  observed ${marker}" >&2
  exit 1
fi
printf '%s\n' "$marker"
