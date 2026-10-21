"""Lambda entry points for the Step Functions workflow (infra/stacks/intake_stack.py).

Brokers' packages land in s3://<intake>/incoming/<submission_id>/...; the
uploader writes manifest.json last, and that object's creation starts the
workflow. Each state calls one Pipeline step. Between states the RunState is
stored in the artifacts bucket, together with the OCR cache, so a scanned page
is OCR'd once. Only small pointers travel through Step Functions, because its
payload limit (256 KB) is far below a full result.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

TMP = Path(os.environ.get("SUBMITIQ_TMP", "/tmp"))
os.environ.setdefault("SUBMITIQ_CACHE", str(TMP / "cache"))

from .pipeline import build_pipeline  # noqa: E402
from .runstate import dump_state, load_state  # noqa: E402

_clients: dict = {}


def clients() -> dict:
    """boto3 clients, created lazily (tests replace this dict with fakes)."""
    if not _clients:
        import boto3
        _clients.update(s3=boto3.client("s3"), ddb=boto3.client("dynamodb"))
    return _clients


def _pipeline():
    return build_pipeline("final", backend=os.environ.get("SUBMITIQ_BACKEND", "bedrock"))


def _sync_down(bucket: str, prefix: str, dest: Path) -> None:
    s3 = clients()["s3"]
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix, **({"ContinuationToken": token} if token else {})}
        page = s3.list_objects_v2(**kw)
        for obj in page.get("Contents", []):
            rel = obj["Key"][len(prefix):].lstrip("/")
            if not rel or rel.endswith("/"):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, obj["Key"], str(target))
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")


def _sync_up(src: Path, bucket: str, prefix: str) -> None:
    s3 = clients()["s3"]
    for f in src.rglob("*"):
        if f.is_file():
            s3.upload_file(str(f), bucket, f"{prefix}/{f.relative_to(src)}")


def _prepare(event: dict) -> tuple[Path, str]:
    sub_id = event["submission_id"]
    pkg = TMP / "pkg" / sub_id
    if not pkg.exists():
        _sync_down(event["bucket"], f"incoming/{sub_id}/", pkg)
        (pkg / "manifest.json").unlink(missing_ok=True)
    _sync_down(os.environ["ARTIFACT_BUCKET"], f"{sub_id}/cache/", Path(os.environ["SUBMITIQ_CACHE"]))
    return pkg, sub_id


def _save(st, event: dict) -> dict:
    art = os.environ["ARTIFACT_BUCKET"]
    sub_id = event["submission_id"]
    clients()["s3"].put_object(Bucket=art, Key=f"{sub_id}/state.json", Body=dump_state(st).encode())
    cache = Path(os.environ["SUBMITIQ_CACHE"])
    if cache.exists():
        _sync_up(cache, art, f"{sub_id}/cache")
    return {"submission_id": sub_id, "bucket": event["bucket"]}


def _load(event: dict):
    pkg, sub_id = _prepare(event)
    obj = clients()["s3"].get_object(Bucket=os.environ["ARTIFACT_BUCKET"], Key=f"{sub_id}/state.json")
    return load_state(obj["Body"].read().decode(), pkg)


# ---------------------------------------------------------------------------- states

def start(event: dict, context=None) -> dict:
    """EventBridge 'Object Created' (manifest.json) -> workflow input."""
    key = event["detail"]["object"]["key"] if "detail" in event else event["key"]
    bucket = event["detail"]["bucket"]["name"] if "detail" in event else event["bucket"]
    parts = key.split("/")
    if len(parts) < 3 or parts[0] != "incoming":
        raise ValueError(f"unexpected key {key}")
    return {"submission_id": parts[1], "bucket": bucket}


def classify(event: dict, context=None) -> dict:
    pkg, _ = _prepare(event)
    pipe = _pipeline()
    st = pipe.start(pkg)
    pipe.classify(st)
    return _save(st, event)


def _step(name: str):
    def handler(event: dict, context=None) -> dict:
        pipe = _pipeline()
        st = _load(event)
        getattr(pipe, name)(st)
        return _save(st, event)
    handler.__name__ = name
    return handler


extract = _step("extract")
validate = _step("validate")
rules = _step("decide")


def summarize(event: dict, context=None) -> dict:
    pipe = _pipeline()
    st = _load(event)
    pipe.summarize(st)
    res = pipe.finish(st)
    sub_id = event["submission_id"]
    art = os.environ["ARTIFACT_BUCKET"]
    clients()["s3"].put_object(Bucket=art, Key=f"{sub_id}/result.json", Body=res.model_dump_json().encode())
    status = "needs_review" if res.needs_review else "auto_cleared"
    item = {
        "submission_id": {"S": sub_id}, "status": {"S": status},
        "decision": {"S": res.decision.outcome or "none"},
        "insured": {"S": res.record.insured.named_insured or ""},
        "flagged_fields": {"N": str(len(res.flagged_paths()))},
        "total_tiv": {"N": str(Decimal(str(res.record.totals.total_tiv or 0)))},
        "result_s3_key": {"S": f"{sub_id}/result.json"},
        "updated_at": {"S": datetime.now(timezone.utc).isoformat()},
    }
    clients()["ddb"].put_item(TableName=os.environ["TABLE_NAME"], Item=item)
    emit_metrics(res)
    return {"submission_id": sub_id, "status": status, "decision": res.decision.outcome}


def mark_failed(event: dict, context=None) -> dict:
    """Catch-all for a failed execution: record it so it shows up as failed, never as silently missing."""
    sub_id = event.get("submission_id", "unknown")
    err = event.get("error", {})
    clients()["ddb"].put_item(TableName=os.environ["TABLE_NAME"], Item={
        "submission_id": {"S": sub_id}, "status": {"S": "failed"},
        "error": {"S": json.dumps(err)[:2000]}, "updated_at": {"S": datetime.now(timezone.utc).isoformat()}})
    print(json.dumps(_emf({"Failed": 1})))
    return {"submission_id": sub_id, "status": "failed"}


def _emf(metrics: dict[str, float]) -> dict:
    return {
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": "SubmitIQ", "Dimensions": [["Pipeline"]],
            "Metrics": [{"Name": k, "Unit": "Milliseconds" if k.endswith("Ms") else "None"} for k in metrics]}]},
        "Pipeline": "final", **metrics,
    }


def emit_metrics(res) -> None:
    """CloudWatch Embedded Metric Format: a structured log line becomes metrics, with no API calls."""
    print(json.dumps(_emf({
        "Processed": 1, "NeedsReview": int(res.needs_review), "Degraded": int(bool(res.degraded_reasons)),
        "FlaggedFields": len(res.flagged_paths()), "LLMCostUsd": round(sum(c.cost_usd for c in res.llm_calls), 6),
        "PipelineLatencyMs": round(sum(res.timings_ms.values()), 1),
        f"Decision_{res.decision.outcome or 'none'}": 1,
    })))
