#!/usr/bin/env python3
"""CDK stack for hackathon log analysis prototype infrastructure."""

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    CustomResource,
    Duration,
    RemovalPolicy,
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
)
from constructs import Construct

SEED_LAMBDA_CODE = '''
import json
import os
import time
import uuid
import random
import boto3
from datetime import datetime, timezone, timedelta

def handler(event, context):
    log_group = os.environ["LOG_GROUP_NAME"]
    client = boto3.client("logs")

    try:
        client.create_log_group(logGroupName=log_group)
    except client.exceptions.ResourceAlreadyExistsException:
        pass

    services = ["api-gateway", "auth-service", "payment-service", "order-service", "inventory-service"]
    now = datetime.now(timezone.utc)
    events = []

    for _ in range(200):
        ts = now - timedelta(minutes=random.randint(0, 120))
        service = random.choice(services)
        is_error = random.random() < 0.08
        entry = {
            "service": service,
            "level": "ERROR" if is_error else "INFO",
            "statusCode": random.choice([500, 504]) if is_error else 200,
            "latencyMs": random.randint(2000, 8000) if is_error else random.randint(20, 300),
            "message": "ERROR: Service failure" if is_error else "INFO: Request processed",
            "traceId": str(uuid.uuid4()),
        }
        events.append({
            "timestamp": int(ts.timestamp() * 1000),
            "message": json.dumps(entry),
        })

    stream = f"seed/{int(time.time())}"
    client.create_log_stream(logGroupName=log_group, logStreamName=stream)
    client.put_log_events(
        logGroupName=log_group,
        logStreamName=stream,
        logEvents=sorted(events, key=lambda e: e["timestamp"]),
    )

    return {
        "Status": "SUCCESS",
        "PhysicalResourceId": stream,
        "Data": {"events": len(events)},
    }
'''


class LogAnalysisInfraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_group_name = "/hackathon/log-analysis/ecommerce-platform"

        log_group = logs.LogGroup(
            self,
            "EcommerceLogGroup",
            log_group_name=log_group_name,
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        agent_policy = iam.ManagedPolicy(
            self,
            "LogAnalysisAgentPolicy",
            managed_policy_name="HackathonLogAnalysisAgentPolicy",
            description="CloudWatch read permissions for log analysis agent",
            statements=[
                iam.PolicyStatement(
                    sid="CloudWatchLogsRead",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                        "logs:FilterLogEvents",
                        "logs:GetLogEvents",
                        "logs:StartQuery",
                        "logs:GetQueryResults",
                        "logs:StopQuery",
                    ],
                    resources=[
                        log_group.log_group_arn,
                        f"{log_group.log_group_arn}:*",
                        "arn:aws:logs:*:*:log-group:/hackathon/*",
                    ],
                ),
                iam.PolicyStatement(
                    sid="CloudWatchMetricsRead",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cloudwatch:GetMetricStatistics",
                        "cloudwatch:ListMetrics",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    sid="BedrockInvoke",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    resources=[
                        "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-*",
                        "arn:aws:bedrock:*:*:inference-profile/us.anthropic.claude-sonnet-*",
                    ],
                ),
            ],
        )

        seed_fn = lambda_.Function(
            self,
            "SeedLogsFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            timeout=Duration.minutes(5),
            code=lambda_.Code.from_inline(SEED_LAMBDA_CODE),
            environment={"LOG_GROUP_NAME": log_group_name},
        )

        log_group.grant_write(seed_fn)

        seed_resource = CustomResource(
            self,
            "SeedLogsResource",
            service_token=seed_fn.function_arn,
        )
        seed_resource.node.add_dependency(log_group)

        CfnOutput(self, "LogGroupName", value=log_group_name)
        CfnOutput(
            self,
            "AgentPolicyArn",
            value=agent_policy.managed_policy_arn,
            description="Attach this policy to the AgentCore runtime IAM role",
        )


app = cdk.App()
LogAnalysisInfraStack(app, "LogAnalysisInfraStack")
app.synth()
