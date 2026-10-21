from evals.run import list_packages, load_gt
from submitiq.llm import LLMResponse
from submitiq.pipeline import VARIANTS, Pipeline
from submitiq.result import Decision
from submitiq.rules_engine import RulesEngine
from submitiq.summary import summarize, template_summary, validate_summary
from tests.fakes import FakeClient


def _gt():
    return load_gt(list_packages("dev")[2])


def test_template_summary_is_valid_for_ground_truth():
    gt = _gt()
    d = RulesEngine().evaluate(gt.record)
    text = template_summary(gt.record, d, {})
    ok, problems = validate_summary(text, gt.record, {str(gt.record.submission_id[-4:])} | {
        m for h in d.reasons for m in h.message.replace("$", "").split()})
    assert ok, problems


def test_validator_rejects_uncited_numbers_and_unknown_fields():
    rec = _gt().record
    ok, problems = validate_summary("TIV is $99,999,999 [totals.total_tiv] [insured.naics_code] [policy.effective_date]", rec)
    assert not ok and any("99,999,999" in p for p in problems)
    ok, problems = validate_summary("x [insured.not_a_field] [totals.total_tiv] [policy.effective_date]", rec)
    assert not ok


def test_bad_llm_summary_falls_back_to_template():
    gt = _gt()
    d = RulesEngine().evaluate(gt.record)
    client = FakeClient(lambda r: LLMResponse(text="Looks great, TIV about $123,456,789. Accept!", model="fake"))
    _, _, text, source, valid = summarize(gt.record, d, {}, client)
    assert source.startswith("template") and valid and "Triage summary" in text


def test_good_llm_summary_is_used():
    gt = _gt()
    rec = gt.record
    d = Decision(outcome="accept", source="rules")
    good = (f"Recommendation: accept. {rec.insured.named_insured} [insured.named_insured], NAICS "
            f"{rec.insured.naics_code} [insured.naics_code], effective {rec.policy.effective_date} [policy.effective_date].")
    _, _, text, source, valid = summarize(rec, d, {}, FakeClient(lambda r: LLMResponse(text=good, model="fake")))
    assert source == "llm" and valid and text == good


def test_final_pipeline_always_decides_and_summarises_offline():
    pkg = list_packages("test")[0]
    res = Pipeline(VARIANTS["final"], FakeClient(lambda r: None)).run(pkg)
    assert res.decision.source == "rules" and res.decision.outcome in ("accept", "refer", "decline")
    assert res.summary and res.summary_citations_valid
