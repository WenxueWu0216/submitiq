# GET /review-queue: measured query optimization

Everything below was measured on 2026-11-05 with the scripts in this folder. The setup was SQL Server 2022
Developer (16.0.4305.5) in Docker (`docker-compose.yml`), on a 4-vCPU / 15 GB Linux container, with a warm buffer pool.
Absolute times depend on the machine. Logical reads do not, and they are the more reliable comparison.

## Dataset (`seed.sql`)

| table | rows |
|---|---|
| Submissions | 100,000 |
| ExtractedFields | 1,000,000 (10 flagged fields per submission) |
| ReviewTasks | 1,000,000 (one per flagged field; 5% open = **50,000 open tasks**) |

Seeding takes 29 s:
`sqlcmd -d SubmitIQ_Perf -v Submissions=100000 TasksPerSubmission=10 OpenPercent=5 -i perf/seed.sql`.

## What was slow

The endpoint runs two queries: `COUNT(*) WHERE Status = 'Open'`, and a page query
`WHERE Status = 'Open' ORDER BY Priority DESC, CreatedAt, Id OFFSET … FETCH 20` that also loads each task's
`ExtractedField`. I took the SQL from EF Core's command log. The actual plans showed two separate problems:

1. **The query shape.** `db.ExtractedFields.FirstOrDefault(f => f.SubmissionId == t.SubmissionId && f.Path == t.FieldPath)`
   inside the projection made EF Core 8 emit `ROW_NUMBER() OVER (PARTITION BY SubmissionId, Path)` over the
   **entire** ExtractedFields table on every request. That cost 1,000,000 index rows, 1,000,000 key lookups
   and **3,088,043 logical reads** to return 20 fields.
2. **No index for the queue's filter and order.** The plan did a clustered scan of all 1,000,000 tasks, kept the
   50,000 open ones, then sorted them to get the top 20.

## Changes

* **A. Query:** page the tasks first, then `LEFT JOIN` ExtractedFields on `(SubmissionId, Path)`. That key is already
  unique, so no "first per group" is needed (`ReviewService.QueueAsync`).
* **B. Index:** `IX_ReviewTasks_Status_Priority_CreatedAt_Id` on `(Status, Priority DESC, CreatedAt, Id)`, added by
  migration `AddReviewQueueIndex`. It matches the WHERE and ORDER BY exactly, so the top 20 rows come straight
  off the index with no sort.

## SQL Server results (page query, `measure_sql.sh` + `plan_summary.py`)

Statement elapsed time and total logical reads for the page query, with `STATISTICS IO/TIME` and the actual plan,
recompiled for each offset. Raw output is in `results/`.

| | page 1 (OFFSET 0) | last page (OFFSET 49,980) |
|---|---|---|
| 1. original query, no index | 2,683 ms, 3,117,408 reads | 2,690 ms, 3,117,408 reads |
| 2. original query + index B | 2,489 ms, 3,088,174 reads | 2,714 ms, 3,117,408 reads |
| 3. query change A, no index | 51 ms, 30,047 reads | 205 ms, 29,505 reads |
| 4. **A + B** | **3 ms, 271 reads** | 211 ms, 29,505 reads |

COUNT query: without the index, 29,847 reads and 39–45 ms. With the index, **252 reads, 3–4 ms**.

Reading the table:
* The index alone (row 2) barely helped, about 7% on page 1, because the field lookup dominated. Profiling before
  indexing is what found the real problem.
* The query change alone (row 3) cut page-1 reads by 99%.
* Together, page 1 goes from 3.1M reads to 271, and every plan operator is a seek touching 20 rows.
* At the last page, the optimizer (with a fresh compile) still scans and sorts the 50,000 open tasks. Skipping 49,980 rows
  via seek + lookups looks more expensive to it. Deep OFFSET paging is the remaining weak spot; see next steps.

## End-to-end HTTP results (`bench_http.py`, Release build, p50 / p95)

| | page 1 | page 100 | page 2,500 (last) | runs per page |
|---|---|---|---|---|
| before (original query, no index) | 2,463 / 2,670 ms | 2,439 / 2,582 ms | 2,422 / 2,526 ms | 20 |
| query change A only | 109 / 133 ms | 130 / 156 ms | 793 / 898 ms | 50 |
| **after (A + B)** | **9.7 / 12.3 ms** | **12.1 / 13.7 ms** | **79.5 / 95.0 ms** | 50 |

That is a p50 of 2,463 → 9.7 ms on the first page, about 250× faster. The HTTP numbers include the COUNT query, JSON
serialization and the HTTP round trip. Through the API, the last page is faster than in the recompiled SQL measurement
(79.5 ms vs 211 ms) because the app reuses the cached plan (index seek + lookups) for every page. Without the index,
the cached plan made the last page *slower* (793 ms). Both are plan-caching effects, and I report them as measured.

## Reproduce

```bash
docker compose up -d
dotnet ef database update --project src/SubmitIQ.Api \
  --connection "Server=localhost,1433;Database=SubmitIQ_Perf;User Id=sa;Password=SubmitIQ_Dev_Passw0rd!;TrustServerCertificate=True"
docker compose cp perf/seed.sql sqlserver:/tmp/seed.sql
docker compose exec -T sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'SubmitIQ_Dev_Passw0rd!' -C \
  -d SubmitIQ_Perf -v Submissions=100000 TasksPerSubmission=10 OpenPercent=5 -i /tmp/seed.sql
perf/measure_sql.sh 0 | python3 perf/plan_summary.py                        # current query
perf/measure_sql.sh 0 perf/review_queue_query_original.sql | python3 perf/plan_summary.py
ConnectionStrings__SubmitIQ="Server=localhost,1433;Database=SubmitIQ_Perf;User Id=sa;Password=SubmitIQ_Dev_Passw0rd!;TrustServerCertificate=True" \
  dotnet run -c Release --project src/SubmitIQ.Api --urls http://localhost:5081 &
python3 perf/bench_http.py http://localhost:5081 --runs 50
```

To measure "without the index", drop it in the perf database
(`DROP INDEX IX_ReviewTasks_Status_Priority_CreatedAt_Id ON ReviewTasks`) and re-run.

## Next step (not done)

Keyset pagination (`WHERE (Priority, CreatedAt, Id) < (last seen)` instead of `OFFSET`) would make every page as
cheap as page 1 on the same index. I haven't built or measured it.
