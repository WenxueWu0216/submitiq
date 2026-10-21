"""CDK stack assertions (no AWS account, no Docker build: synth only stages the asset)."""
import sys
from pathlib import Path

import pytest

cdk = pytest.importorskip("aws_cdk")
from aws_cdk.assertions import Match, Template  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra"))
from stacks.intake_stack import IntakeStack  # noqa: E402


@pytest.fixture(scope="module")
def template():
    app = cdk.App(context={"bedrockModelId": "anthropic.claude-opus-5-5"})
    return Template.from_stack(IntakeStack(app, "T"))


def test_workflow_states_in_order(template):
    sm = template.find_resources("AWS::StepFunctions::StateMachine")
    body = str(next(iter(sm.values()))["Properties"]["DefinitionString"])
    order = [body.index(f'"{s}":{{') for s in ("Start", "Classify", "Extract", "Validate", "Rules", "Summarize")]
    assert order == sorted(order) and "MarkFailed" in body


def test_data_is_encrypted_and_private(template):
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketEncryption": Match.object_like({"ServerSideEncryptionConfiguration": Match.any_value()}),
        "PublicAccessBlockConfiguration": {"BlockPublicAcls": True, "BlockPublicPolicy": True,
                                           "IgnorePublicAcls": True, "RestrictPublicBuckets": True}})
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "SSESpecification": Match.object_like({"SSEEnabled": True}),
        "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True}})


def test_manifest_upload_triggers_workflow(template):
    template.has_resource_properties("AWS::Events::Rule", {"EventPattern": Match.object_like({
        "detail-type": ["Object Created"],
        "detail": Match.object_like({"object": {"key": [{"wildcard": "incoming/*/manifest.json"}]}})})})


def test_bedrock_permission_is_scoped_to_the_model(template):
    pols = template.find_resources("AWS::IAM::Policy")
    stmts = [s for p in pols.values() for s in p["Properties"]["PolicyDocument"]["Statement"]
             if "bedrock:InvokeModel" in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])]
    assert stmts and all("*" != r for s in stmts for r in (s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]))
