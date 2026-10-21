from evals.metrics import score
from evals.run import list_packages, load_gt
from submitiq.pipeline import VARIANTS, Pipeline
from tests.fakes import FakeClient, baseline_answer_from


def test_baseline_round_trips_a_perfect_model_answer():
    pkg = list_packages("dev")[1]
    gt = load_gt(pkg)
    client = FakeClient(baseline_answer_from(gt))
    res = Pipeline(VARIANTS["baseline"], client).run(pkg)
    s = score(gt, res)
    assert s.overall.prf()["f1"] == 1.0
    assert res.decision.outcome == gt.meta.expected_decision
    # one baseline call; every document carried into the prompt
    req = next(r for r in client.requests if r.task == "baseline_extract")
    for name in gt.meta.doc_types:
        assert f'name="{name}"' in req.user


def test_baseline_abstains_and_routes_to_review_on_replay_miss():
    pkg = list_packages("dev")[0]
    res = Pipeline(VARIANTS["baseline"], FakeClient(lambda r: None)).run(pkg)
    assert res.needs_review and res.decision.outcome is None
    assert res.record.insured.named_insured is None
