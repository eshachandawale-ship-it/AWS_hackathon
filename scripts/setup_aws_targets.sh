#!/usr/bin/env bash
# Write agentcore/aws-targets.json from current AWS credentials.
set -euo pipefail

cd "$(dirname "$0")/.."

REGION="${AWS_REGION:-us-west-2}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text --region "$REGION")

if [[ ! "$ACCOUNT" =~ ^[0-9]{12}$ ]]; then
  echo "ERROR: Could not resolve 12-digit AWS account ID (got: '$ACCOUNT')"
  exit 1
fi

cat > agentcore/aws-targets.json <<EOF
[
  {
    "name": "default",
    "description": "AWS Hackathon workshop environment",
    "account": "$ACCOUNT",
    "region": "$REGION"
  }
]
EOF

echo "Updated agentcore/aws-targets.json → account=$ACCOUNT region=$REGION"
