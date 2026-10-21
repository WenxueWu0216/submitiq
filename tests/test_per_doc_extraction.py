"""The tool-use path, driven by a fake 'perfect' model, must reconstruct the record.

This exercises every tool schema -> DocExtraction -> assemble mapping without
network access. It does not say anything about how well Claude itself does.
"""
import json

import pytest

from evals.metrics import score
from evals.run import list_packages, load_gt
from submitiq.extract.llm_docs import TOOLS
from submitiq.pipeline import VARIANTS, Pipeline
from tests.fakes import FakeClient, tool_answers_from


def _template_c_package():
    return next(p for p in list_packages("test") if load_gt(p).meta.template == "C")


@pytest.mark.parametrize("variant", ["v2_tooluse"])
def test_fake_perfect_model_closes_template_c_gap(variant):
    pkg = _template_c_package()
    gt = load_gt(pkg)
    offline = score(gt, Pipeline(VARIANTS[variant], FakeClient(lambda r: None)).run(pkg)).overall.prf()["f1"]
    res = Pipeline(VARIANTS[variant], FakeClient(tool_answers_from(gt))).run(pkg)
    with_model = score(gt, res).overall.prf()["f1"]
    assert with_model > offline
    assert with_model >= 0.97
    assert res.decision.outcome == gt.meta.expected_decision


def test_every_llm_value_carries_page_and_evidence():
    pkg = _template_c_package()
    gt = load_gt(pkg)
    res = Pipeline(VARIANTS["v2_tooluse"], FakeClient(tool_answers_from(gt))).run(pkg)
    llm_fields = [p for p in res.provenance.values() if p.extractor and p.extractor.startswith("llm:")]
    assert llm_fields
    assert all(p.citations and p.citations[0].doc and p.citations[0].snippet for p in llm_fields)


def _walk(schema, path="$"):
    yield path, schema
    for k, v in schema.get("properties", {}).items():
        yield from _walk(v, f"{path}.{k}")
    if "items" in schema:
        yield from _walk(schema["items"], f"{path}[]")


def test_tool_schemas_are_strict_compatible():
    for tool in TOOLS.values():
        json.dumps(tool)
        for path, node in _walk(tool["input_schema"]):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, path
                assert set(node["required"]) == set(node["properties"]), path
