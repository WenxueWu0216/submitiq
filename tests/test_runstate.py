"""Running the steps with a JSON round trip between each (as on AWS) must equal a local run."""
from evals.run import list_packages
from submitiq.pipeline import VARIANTS, Pipeline
from submitiq.runstate import dump_state, load_state
from tests.fakes import FakeClient


def _strip(res):
    d = res.model_dump(mode="json")
    d.pop("timings_ms")
    return d


def test_step_by_step_with_serialization_matches_local_run():
    pkg = next(p for p in list_packages("dev") if p.name == "SUB-0016")   # year-built conflict
    pipe = Pipeline(VARIANTS["final"], FakeClient(lambda r: None))
    local = pipe.run(pkg)
    st = pipe.start(pkg)
    for step in (pipe.classify, pipe.extract, pipe.validate, pipe.decide, pipe.summarize):
        step(st)
        st = load_state(dump_state(st), pkg)    # what the next Lambda sees
    remote = pipe.finish(st)
    assert _strip(remote) == _strip(local)
