from datetime import date

from submitiq.consistency import check
from submitiq.extract.types import DocExtraction
from submitiq.normalize import parse_bool, parse_construction, parse_date, parse_money, same_entity
from submitiq.result import Candidate, Citation, FieldProvenance


def test_money_formats():
    assert parse_money("$1,250,000") == 1_250_000
    assert parse_money("$1.25M") is None            # basic mode does not guess
    assert parse_money("$1.25M", "full") == 1_250_000
    assert parse_money("S12,500.00", "full") == 12_500  # OCR read '$' as 'S'


def test_construction_synonyms_only_in_full_mode():
    assert parse_construction("Joisted Masonry") == "joisted_masonry"
    assert parse_construction("JM") is None
    assert parse_construction("JM", "full") == "joisted_masonry"
    assert parse_construction("ISO 4", "full") == "masonry_non_combustible"


def test_dates_and_bools():
    assert parse_date("January 5, 2027", "full") == date(2027, 1, 5)
    assert parse_date("January 5, 2027") is None
    assert parse_bool("Yes", "full") is True and parse_bool("Yes") is None


def test_entity_matching():
    assert same_entity("Acme Logistics LLC", "ACME LOGISTICS, L.L.C.")
    assert same_entity("Acme LLC", "ACME Holdings")
    assert same_entity("Harbor Point Logistics LLC", "Harbor Point")
    assert not same_entity("Harbor Point Logistics LLC", "Harbor Point Distribution Inc.")


def _cite(doc):
    return Citation(doc=doc, doc_type="x")


def test_cross_document_conflict_is_flagged_but_value_kept():
    prov = {"locations[1].year_built": FieldProvenance(
        path="locations[1].year_built", extractor="table_parser:local", citations=[_cite("sov.xlsx")],
        alternatives=[Candidate(value=1987, extractor="form_parser:premises", citation=_cite("app.pdf"))])}
    reasons = check(prov, {"locations[1].year_built": 1994}, [], "full")
    assert prov["locations[1].year_built"].status == "conflict" and reasons


def test_name_variant_is_not_a_conflict_but_a_different_entity_is():
    def run(printed):
        prov = {"insured.named_insured": FieldProvenance(path="insured.named_insured", citations=[_cite("app.pdf")])}
        ex = DocExtraction("lr.pdf", "loss_run", "table_parser:local", names=[(printed, _cite("lr.pdf"))])
        check(prov, {"insured.named_insured": "Cedar Lane Logistics LLC"}, [ex], "full")
        return prov["insured.named_insured"].status
    assert run("CEDAR LANE HOLDINGS") == "ok"
    assert run("Cedar Lane Distribution Inc.") == "conflict"
