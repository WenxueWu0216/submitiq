#!/usr/bin/env python3
"""CDK app. `cdk synth` works without AWS credentials (account/region stay unresolved tokens)."""
import os

import aws_cdk as cdk

from stacks.intake_stack import IntakeStack

app = cdk.App()
IntakeStack(
    app, "SubmitIQ",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=os.environ.get("CDK_DEFAULT_REGION")),
    description="SubmitIQ insurance submission intake: S3 -> Step Functions -> Lambda (Bedrock) -> DynamoDB",
)
app.synth()
