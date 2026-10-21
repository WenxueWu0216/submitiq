"""S3 intake -> EventBridge -> Step Functions (classify -> extract -> validate -> rules -> summarize)
-> DynamoDB, with Bedrock for Claude, KMS encryption everywhere and CloudWatch metrics/alarms."""
from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput, Duration, RemovalPolicy, Stack,
    aws_cloudwatch as cw, aws_cloudwatch_actions as cw_actions, aws_dynamodb as ddb, aws_ecr_assets as ecr_assets,
    aws_events as events, aws_events_targets as targets, aws_iam as iam, aws_kms as kms, aws_lambda as lambda_,
    aws_logs as logs, aws_s3 as s3, aws_sns as sns, aws_sns_subscriptions as subs,
    aws_stepfunctions as sfn, aws_stepfunctions_tasks as tasks,
)
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]

# memory (MB), timeout (s), reserved concurrency (None = unreserved)
STEPS = {
    "start": (256, 30, None),
    "classify": (2048, 300, None),       # text extraction + OCR
    "extract": (1536, 600, 20),          # Bedrock calls; cap concurrency to stay inside model quotas
    "validate": (1024, 120, None),
    "rules": (512, 60, None),
    "summarize": (1024, 300, 20),        # Bedrock call
    "mark_failed": (256, 30, None),
}


class IntakeStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kw) -> None:
        super().__init__(scope, cid, **kw)
        model_id = self.node.try_get_context("bedrockModelId") or "anthropic.claude-opus-5-5"
        alarm_email = self.node.try_get_context("alarmEmail") or ""

        key = kms.Key(self, "DataKey", enable_key_rotation=True, alias="alias/submitiq-data",
                      description="Encrypts submission documents, artifacts and records")

        intake = s3.Bucket(
            self, "IntakeBucket", encryption=s3.BucketEncryption.KMS, encryption_key=key, bucket_key_enabled=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True, versioned=True,
            event_bridge_enabled=True, removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[s3.LifecycleRule(transitions=[s3.Transition(
                storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL, transition_after=Duration.days(90))])],
        )
        artifacts = s3.Bucket(
            self, "ArtifactBucket", encryption=s3.BucketEncryption.KMS, encryption_key=key, bucket_key_enabled=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True, removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[s3.LifecycleRule(prefix="", expiration=Duration.days(400))],
        )
        table = ddb.Table(
            self, "Submissions", partition_key=ddb.Attribute(name="submission_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST, encryption=ddb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=key, point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True), removal_policy=RemovalPolicy.RETAIN,
        )
        table.add_global_secondary_index(index_name="by_status",
                                         partition_key=ddb.Attribute(name="status", type=ddb.AttributeType.STRING),
                                         sort_key=ddb.Attribute(name="updated_at", type=ddb.AttributeType.STRING))

        image = ecr_assets.DockerImageAsset(
            self, "WorkerImage", directory=str(REPO_ROOT), file="infra/Dockerfile.lambda",
            platform=ecr_assets.Platform.LINUX_AMD64,
            exclude=["data", ".git", ".venv", ".cache", "infra/cdk.out", "evals", "fixtures", "service", "tests",
                     "docs", "**/__pycache__", "*.db"],
        )
        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}",
                       f"arn:aws:bedrock:*::foundation-model/{model_id}",
                       f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*{model_id}*"],
        )
        env = {"ARTIFACT_BUCKET": artifacts.bucket_name, "TABLE_NAME": table.table_name,
               "SUBMITIQ_BACKEND": "bedrock", "SUBMITIQ_BEDROCK_MODEL_ID": model_id,
               "POWERTOOLS_SERVICE_NAME": "submitiq"}

        fns: dict[str, lambda_.DockerImageFunction] = {}
        for name, (mem, timeout, reserved) in STEPS.items():
            fn = lambda_.DockerImageFunction(
                self, f"{name.title().replace('_', '')}Fn",
                code=lambda_.DockerImageCode.from_ecr(image.repository, tag_or_digest=image.image_tag,
                                                      cmd=[f"submitiq.aws_handlers.{name}"]),
                memory_size=mem, timeout=Duration.seconds(timeout), reserved_concurrent_executions=reserved,
                environment=env, architecture=lambda_.Architecture.X86_64,
                tracing=lambda_.Tracing.ACTIVE,
                log_group=logs.LogGroup(self, f"{name.title().replace('_', '')}Logs", retention=logs.RetentionDays.ONE_YEAR),
            )
            intake.grant_read(fn)
            artifacts.grant_read_write(fn)
            table.grant_write_data(fn)
            if name in ("extract", "summarize", "classify"):
                fn.add_to_role_policy(bedrock_policy)
            fns[name] = fn

        def step(name: str) -> tasks.LambdaInvoke:
            t = tasks.LambdaInvoke(self, name.title(), lambda_function=fns[name], payload_response_only=True,
                                   retry_on_service_exceptions=True)
            # Model throttling / transient errors: back off and retry before giving up.
            t.add_retry(errors=["States.TaskFailed"], interval=Duration.seconds(5), max_attempts=3, backoff_rate=2.0)
            return t

        failed = tasks.LambdaInvoke(self, "MarkFailed", lambda_function=fns["mark_failed"], payload_response_only=True,
                                    payload=sfn.TaskInput.from_object({
                                        "submission_id": sfn.JsonPath.string_at("$.submission_id"),
                                        "error": sfn.JsonPath.object_at("$.error")})).next(
            sfn.Fail(self, "Failed", cause="submission processing failed; recorded as status=failed"))

        chain = step("start")
        last = chain
        for name in ("classify", "extract", "validate", "rules", "summarize"):
            nxt = step(name)
            nxt.add_catch(failed, result_path="$.error")
            last.next(nxt)
            last = nxt
        last.next(sfn.Succeed(self, "Done"))

        sm_logs = logs.LogGroup(self, "WorkflowLogs", retention=logs.RetentionDays.ONE_YEAR)
        machine = sfn.StateMachine(
            self, "IntakeWorkflow", definition_body=sfn.DefinitionBody.from_chainable(chain),
            timeout=Duration.minutes(30), tracing_enabled=True,
            logs=sfn.LogOptions(destination=sm_logs, level=sfn.LogLevel.ERROR),
        )

        # manifest.json is written last by the uploader: one execution per complete package.
        events.Rule(
            self, "ManifestUploaded",
            event_pattern=events.EventPattern(
                source=["aws.s3"], detail_type=["Object Created"],
                detail={"bucket": {"name": [intake.bucket_name]},
                        "object": {"key": [{"wildcard": "incoming/*/manifest.json"}]}}),
            targets=[targets.SfnStateMachine(machine)],
        )

        # ------------------------------------------------------------------ observability
        topic = sns.Topic(self, "Alarms", master_key=key)
        if alarm_email:
            topic.add_subscription(subs.EmailSubscription(alarm_email))
        metric = lambda name, stat="Sum", minutes=15: cw.Metric(
            namespace="SubmitIQ", metric_name=name, statistic=stat, dimensions_map={"Pipeline": "final"},
            period=Duration.minutes(minutes))
        alarms = [
            cw.Alarm(self, "WorkflowFailures", metric=machine.metric_failed(period=Duration.minutes(15)), threshold=1,
                     evaluation_periods=1, alarm_description="A submission failed processing (status=failed in DynamoDB)."),
            cw.Alarm(self, "ModelDegraded", metric=metric("Degraded"), threshold=5, evaluation_periods=1,
                     treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
                     alarm_description="5+ submissions in 15 min ran without the model (Bedrock errors/throttling)."),
            cw.Alarm(self, "ReviewRateHigh", metric=cw.MathExpression(
                expression="IF(processed > 0, 100 * review / processed, 0)",
                using_metrics={"review": metric("NeedsReview", minutes=60), "processed": metric("Processed", minutes=60)},
                period=Duration.hours(1)), threshold=80, evaluation_periods=3,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
                alarm_description="Review-queue rate above 80% for 3 hours: data drift or an extraction regression."),
        ]
        for a in alarms:
            a.add_alarm_action(cw_actions.SnsAction(topic))

        cw.Dashboard(self, "Dashboard", dashboard_name="SubmitIQ", widgets=[[
            cw.GraphWidget(title="Submissions", left=[metric("Processed"), metric("NeedsReview"), metric("Degraded")]),
            cw.GraphWidget(title="Decisions", left=[metric("Decision_accept"), metric("Decision_refer"), metric("Decision_decline")]),
            cw.GraphWidget(title="LLM cost (USD)", left=[metric("LLMCostUsd")]),
            cw.GraphWidget(title="Pipeline latency (ms)", left=[metric("PipelineLatencyMs", "p50"), metric("PipelineLatencyMs", "p95")]),
        ]])

        CfnOutput(self, "IntakeBucketName", value=intake.bucket_name)
        CfnOutput(self, "ArtifactBucketName", value=artifacts.bucket_name)
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "StateMachineArn", value=machine.state_machine_arn)
