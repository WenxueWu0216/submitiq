import json

from evals.gate import main as gate
from submitiq.llm import LLMRequest, LLMResponse
from submitiq.llm.replay import RecordingClient, ReplayClient


def _run(tmp_path, f1, acc):
    p = tmp_path / f"r{f1}.json"
    p.write_text(json.dumps({"meta": {"pipeline": "final", "split": "all", "backend": "replay", "git_sha": "x",
                                      "timestamp": "t"},
                             "metrics": {"fields": {"overall": {"f1": f1}}, "decision": {"accuracy": acc}}}))
    return str(p)


def test_gate_fails_on_regression_over_two_points(tmp_path):
    base = str(tmp_path / "baseline.json")
    assert gate([_run(tmp_path, 0.95, 0.90), "--baseline", base, "--update"]) == 0
    assert gate([_run(tmp_path, 0.935, 0.90), "--baseline", base]) == 0      # -1.5 pts: ok
    assert gate([_run(tmp_path, 0.925, 0.90), "--baseline", base]) == 1      # -2.5 pts: fail
    assert gate([_run(tmp_path, 0.95, 0.87), "--baseline", base]) == 1


class _Live:
    def __init__(self):
        self.calls = 0

    def complete(self, req):
        self.calls += 1
        return LLMResponse(text="hello", model="claude-opus-5-5", input_tokens=10, output_tokens=2)


def test_record_then_replay(tmp_path):
    req = LLMRequest(task="t", prompt_version="v1", system="s", user="u", key_material="k")
    live = _Live()
    rec = RecordingClient(live, tmp_path)
    assert rec.complete(req).text == "hello" and rec.complete(req).source == "replay:recorded"
    assert live.calls == 1                                       # second call reused the recording
    replayed = ReplayClient(tmp_path).complete(req)
    assert replayed.text == "hello" and replayed.source == "replay:recorded"
    miss = ReplayClient(tmp_path).complete(req.model_copy(update={"key_material": "other"}))
    assert miss.source == "replay:miss" and not miss.ok
