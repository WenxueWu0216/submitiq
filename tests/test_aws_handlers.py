"""The Lambda chain against in-memory fakes of S3 and DynamoDB (no AWS account needed)."""
import importlib
import json
from pathlib import Path

from evals.run import list_packages


class FakeS3:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        data = self.objects[(Bucket, Key)]

        class _B:
            def read(self_inner):
                return data
        return {"Body": _B()}

    def list_objects_v2(self, Bucket, Prefix, **_):
        return {"Contents": [{"Key": k} for (b, k) in sorted(self.objects) if b == Bucket and k.startswith(Prefix)],
                "IsTruncated": False}

    def download_file(self, Bucket, Key, Filename):
        Path(Filename).write_bytes(self.objects[(Bucket, Key)])

    def upload_file(self, Filename, Bucket, Key):
        self.objects[(Bucket, Key)] = Path(Filename).read_bytes()


class FakeDDB:
    def __init__(self):
        self.items = {}

    def put_item(self, TableName, Item):
        self.items[Item["submission_id"]["S"]] = Item


def test_lambda_chain_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUBMITIQ_TMP", str(tmp_path))
    monkeypatch.setenv("SUBMITIQ_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("ARTIFACT_BUCKET", "artifacts")
    monkeypatch.setenv("TABLE_NAME", "submissions")
    monkeypatch.setenv("SUBMITIQ_BACKEND", "replay")
    import submitiq.aws_handlers as h
    importlib.reload(h)
    s3, ddb = FakeS3(), FakeDDB()
    h._clients.update(s3=s3, ddb=ddb)

    pkg = next(p for p in list_packages("dev") if p.name == "SUB-0029")   # rotated scanned SOV + scanned loss run
    for f in pkg.iterdir():
        if f.name != "ground_truth.json":
            s3.put_object("intake", f"incoming/SUB-0029/{f.name}", f.read_bytes())
    s3.put_object("intake", "incoming/SUB-0029/manifest.json", b"{}")

    event = {"detail": {"bucket": {"name": "intake"}, "object": {"key": "incoming/SUB-0029/manifest.json"}}}
    state = h.start(event)
    for step in (h.classify, h.extract, h.validate, h.rules):
        state = step(state)
        assert len(json.dumps(state)) < 1000          # only pointers travel through Step Functions
    out = h.summarize(state)

    from submitiq.pipeline import build_pipeline
    local = build_pipeline("final").run(pkg)
    assert out["decision"] == local.decision.outcome
    item = ddb.items["SUB-0029"]
    assert item["status"]["S"] == out["status"]
    assert ("artifacts", "SUB-0029/result.json") in s3.objects
    assert any(k.startswith("SUB-0029/cache/ocr/") for (_, k) in s3.objects)   # OCR cache shared between steps
    emf = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    assert emf and emf[-1]["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "SubmitIQ"
