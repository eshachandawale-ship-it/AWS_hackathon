"""Configuration for the Log Analysis Agent."""

import os

# Claude Sonnet 4 on Amazon Bedrock
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-20250514-v1:0",
)

# Default log group for the hackathon prototype (synthetic data)
DEFAULT_LOG_GROUP = os.environ.get(
    "LOG_GROUP_NAME",
    "/hackathon/log-analysis/ecommerce-platform",
)

# CloudWatch Logs Insights query timeout (seconds)
INSIGHTS_QUERY_TIMEOUT = int(os.environ.get("INSIGHTS_QUERY_TIMEOUT", "30"))

# AWS region
AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))
