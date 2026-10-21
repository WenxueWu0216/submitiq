"""Write a hand-written replay fixture for one LLM call of one submission.

    python scripts/make_fixture.py SUB-0003 extract_email --show                 # print the request
    python scripts/make_fixture.py SUB-0003 extract_email --response resp.json   # save fixture

The fixture is stored with "source": "hand_written". Every eval and the UI report
that source, so hand-written answers can never pass for real model output.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from submitiq.llm import LLMRequest, LLMResponse, get_client  # noqa: E402
from submitiq.llm.base import replay_dir  # noqa: E402
from submitiq.llm.replay import fixture_path  # noqa: E402
from submitiq.pipeline import VARIANTS, Pipeline  # noqa: E402


class Capture:
    def __init__(self, inner):
        self.inner, self.requests = inner, []

    def complete(self, req: LLMRequest) -> LLMResponse:
        self.requests.append(req)
        return self.inner.complete(req)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission")
    ap.add_argument("task")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--response", help="JSON file: {'text': ...} or {'tool_input': {...}}")
    args = ap.parse_args()
    pkg = next((ROOT / "data" / "submissions").glob(f"*/{args.submission}"))
    cap = Capture(get_client("replay"))
    Pipeline(VARIANTS["final"], cap).run(pkg)
    req = next(r for r in cap.requests if r.task == args.task)
    path = fixture_path(replay_dir(), req)
    if args.show or not args.response:
        print(f"# fixture path: {path.relative_to(ROOT)}\n# system:\n{req.system}\n# user:\n{req.user}")
        return
    resp = json.loads(Path(args.response).read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "task": req.task, "prompt_version": req.prompt_version, "key_material": req.key_material,
        "source": "hand_written", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "note": "Hand-written for the offline demo by reading the document. NOT real model output.",
        "response": {"text": resp.get("text"), "tool_input": resp.get("tool_input"), "model": "hand-written",
                     "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0, "stop_reason": "end_turn"},
    }, indent=1))
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
