from datetime import date

import pytest

from data.synth.labels import AppetiteLabels
from evals.run import list_packages, load_gt
from submitiq.result import FieldProvenance
from submitiq.rules_engine import RulesEngine
from submitiq.schema import Claim, Insured, Location, LossYear, PolicyInfo, Submission, Totals

ENGINE = RulesEngine()


def clean(**loc_overrides) -> Submission:
    loc = dict(loc_number=1, street="1 Main St", city="Columbus", state="OH", zip="43215", construction="masonry_non_combustible",
               year_built=1995, protection_class=3, sprinklered=True, roof_year=2020, tiv=2_000_000.0)
    loc.update(loc_overrides)
    return Submission(
        submission_id="T", insured=Insured(naics_code="493110"), policy=PolicyInfo(effective_date=date(2027, 1, 1)),
        locations=[Location(**loc)], totals=Totals(total_tiv=loc["tiv"]),
        loss_years=[LossYear(policy_year=2022 + i, earned_premium=10_000.0) for i in range(5)])


def ids(rec):
    d = ENGINE.evaluate(rec)
    return d.outcome, sorted({h.rule_id for h in d.reasons})


def test_clean_risk_is_accepted():
    assert ids(clean()) == ("accept", [])


@pytest.mark.parametrize("naics,expected", [("325920", "decline"), ("721110", "refer"), ("999999", "refer")])
def test_class_rules(naics, expected):
    rec = clean()
    rec.insured.naics_code = naics
    assert ids(rec)[0] == expected


def test_missing_required_field_refers_and_names_the_field():
    d = ENGINE.evaluate(clean(protection_class=None))
    assert d.outcome == "refer"
    assert d.reasons[0].rule_id == "MISSING_INFO" and "locations[1].protection_class" in d.reasons[0].fields


def test_frame_with_poor_protection_declines():
    assert ids(clean(construction="frame", protection_class=9)) == ("decline", ["FRAME_POOR_PROTECTION"])
    assert ids(clean(construction="frame", protection_class=8))[0] == "accept"


def test_pc10_refers_and_most_severe_wins():
    outcome, rules = ids(clean(construction="frame", protection_class=10))
    assert outcome == "decline" and rules == ["FRAME_POOR_PROTECTION", "POOR_PROTECTION"]


def test_hurricane_zone():
    assert ids(clean(zip="33101", construction="frame", protection_class=4))[0] == "decline"
    assert ids(clean(zip="33101", tiv=6_000_000.0))[0] == "refer"
    assert ids(clean(zip="33101", tiv=4_000_000.0))[0] == "accept"


def test_earthquake_zone_old_joisted_masonry():
    assert ids(clean(zip="94110", construction="joisted_masonry", year_built=1975)) == ("refer", ["EARTHQUAKE_ZONE"])
    assert ids(clean(zip="94110", construction="joisted_masonry", year_built=1985))[0] == "accept"


def test_tiv_thresholds_are_strictly_greater_than():
    assert ids(clean(tiv=25_000_000.0))[0] == "accept"
    assert ids(clean(tiv=25_000_001.0))[0] == "refer"
    assert ids(clean(tiv=50_000_001.0))[0] == "decline"


def test_unsprinklered_large_location():
    assert ids(clean(sprinklered=False, tiv=12_000_000.0)) == ("refer", ["UNSPRINKLERED"])


def test_age_rules():
    assert ids(clean(year_built=1940, roof_year=2020)) == ("refer", ["BUILDING_AGE"])
    assert ids(clean(roof_year=2000)) == ("refer", ["ROOF_AGE"])


def _with_losses(amounts):
    rec = clean()
    rec.claims = [Claim(claim_number=f"C{i}", policy_year=2023, incurred=a) for i, a in enumerate(amounts)]
    return rec


def test_loss_rules():
    assert ids(_with_losses([30_000.0]))[0] == "accept"            # LR 60% exactly is not > 60%
    assert ids(_with_losses([30_001.0])) == ("refer", ["LOSS_RATIO"])
    assert ids(_with_losses([50_001.0])) == ("decline", ["LOSS_RATIO"])
    assert ids(_with_losses([1_000.0] * 5)) == ("refer", ["LOSS_FREQUENCY"])


def test_large_loss():
    rec = clean()
    for y in rec.loss_years:
        y.earned_premium = 1_000_000.0
    rec.claims = [Claim(claim_number="BIG1", policy_year=2024, incurred=260_000.0, cause="Fire")]
    assert ids(rec) == ("refer", ["LARGE_LOSS"])


def test_decision_caveat_when_relied_on_field_is_flagged():
    rec = clean(construction="frame", protection_class=9)
    prov = {"locations[1].protection_class": FieldProvenance(path="locations[1].protection_class", status="low_confidence")}
    d = ENGINE.evaluate(rec, prov)
    assert "depends on fields under review" in d.reasons[0].message


def test_engine_agrees_with_independent_labeler_on_every_ground_truth_record():
    labeler = AppetiteLabels.load()
    for pkg in list_packages("all"):
        gt = load_gt(pkg)
        d = ENGINE.evaluate(gt.record)
        expected, reasons = labeler.label(gt.record)
        assert d.outcome == expected == gt.meta.expected_decision, pkg.name
        assert sorted({h.rule_id for h in d.reasons}) == reasons, pkg.name
