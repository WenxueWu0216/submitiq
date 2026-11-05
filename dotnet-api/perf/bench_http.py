"""End-to-end timing of GET /review-queue against a running API (perf/README.md).

    python3 perf/bench_http.py http://localhost:5081 [--runs 20]

Requests pages 1, 100 and 2500 (page_size=20; 2500 is the last page of the 50,000-task queue).
Warm-up requests are discarded. Prints p50 / p95 / mean in milliseconds per page.
"""
import argparse
import json
import statistics
import time
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("base")
ap.add_argument("--runs", type=int, default=20)
ap.add_argument("--warmup", type=int, default=3)
args = ap.parse_args()

results = {}
for page in (1, 100, 2500):
    url = f"{args.base}/review-queue?status=open&page={page}&page_size=20"
    times = []
    for i in range(args.warmup + args.runs):
        t0 = time.perf_counter()
        with urllib.request.urlopen(url) as r:
            body = json.loads(r.read())
        dt = (time.perf_counter() - t0) * 1000
        assert len(body["items"]) == 20 and body["total_count"] == 50000, body.get("total_count")
        if i >= args.warmup:
            times.append(dt)
    times.sort()
    p95 = times[min(len(times) - 1, round(0.95 * (len(times) - 1)))]
    results[page] = (statistics.median(times), p95, statistics.mean(times))
    print(f"page {page:>5}: p50 {results[page][0]:8.1f} ms   p95 {p95:8.1f} ms   mean {results[page][2]:8.1f} ms   (n={len(times)})")
