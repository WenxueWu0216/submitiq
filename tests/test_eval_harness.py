"""The harness must score perfect predictions as perfect and empty ones as zero."""
from datetime import date

from evals.matching import align, values_match
from evals.metrics import aggregate, score
from evals.run import list_packages, load_gt
from submitiq.result import PipelineResult
from submitiq.schema import Claim, Submission


def _oracle(gt) -> PipelineResult:
    res = PipelineResult(submission_id=gt.record.submission_id, pipeline="oracle", record=gt.record,
                         doc_types=dict(gt.meta.doc_types))
    res.decision.outcome = gt.meta.expected_decision
    return res


def test_oracle_scores_perfect_on_all_submissions():
    scores = [score(load_gt(p), _oracle(load_gt(p))) for p in list_packages("all")]
    agg = aggregate(scores)
    assert agg["n_submissions"] == 120
    assert agg["fields"]["overall"]["f1"] == 1.0
    assert agg["decision"]["accuracy"] == 1.0
    assert agg["documents"]["classification_accuracy"] == 1.0


def test_empty_prediction_scores_zero():
    gt = load_gt(list_packages("dev")[0])
    empty = PipelineResult(submission_id="x", pipeline="null", record=Submission(submission_id="x"))
    s = score(gt, empty)
    assert s.overall.tp == 0 and s.overall.fp == 0 and s.overall.fn > 30


def test_wrong_value_counts_as_fp_and_fn():
    gt = load_gt(list_packages("dev")[0])
    rec = gt.record.model_copy(deep=True)
    rec.insured.naics_code = "999999"
    s = score(gt, PipelineResult(submission_id="x", pipeline="t", record=rec))
    assert s.overall.fp == 1 and s.overall.fn == 1
    assert s.critical_error


def test_value_matching_is_format_tolerant_but_meaning_strict():
    assert values_match("locations[1].street", "12 Main Street", "12 MAIN ST.")
    assert values_match("coverage.building_limit", 1_250_000.0, 1_250_400.0)
    assert not values_match("coverage.building_limit", 1_250_000.0, 1_300_000.0)
    assert values_match("insured.fein", "12-3456789", "123456789")
    assert not values_match("locations[1].year_built", 1987, 1988)
    assert values_match("insured.website", "www.acme.com", "https://acme.com/")
    assert not values_match("insured.named_insured", "Acme Logistics LLC", "Acme Holdings")


def test_claims_align_by_date_when_claim_number_is_misread():
    gold = Submission(submission_id="x", claims=[Claim(claim_number="CMI-2023-00412", date_of_loss=date(2023, 5, 1), incurred=1000.0)])
    pred = Submission(submission_id="x", claims=[Claim(claim_number="CMl-2O23-0O412", date_of_loss=date(2023, 5, 1), incurred=1000.0)])
    assert align(gold, pred).claims[0].claim_number == "CMI-2023-00412"
