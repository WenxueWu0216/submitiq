#!/usr/bin/env bash
# Runs the review-queue SQL that EF Core generates (perf/review_queue_query.sql) on the perf database
# with STATISTICS IO/TIME and the actual plan (STATISTICS XML). Usage: perf/measure_sql.sh <offset> [query.sql]
set -euo pipefail
cd "$(dirname "$0")/.."
OFFSET=${1:-0}
QUERY=${2:-perf/review_queue_query.sql}
docker compose cp "$QUERY" sqlserver:/tmp/review_queue_query.sql >/dev/null
docker compose exec -T sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'SubmitIQ_Dev_Passw0rd!' -C \
  -d SubmitIQ_Perf -y 0 -v Offset="$OFFSET" -i /tmp/review_queue_query.sql
