#!/usr/bin/env bash
# Phase 1: Deploy runtime + short-term memory only (no evaluators).
# Use this when full deploy fails with NoStack / CREATE_FAILED.
set -euo pipefail

cd "$(dirname "$0")/.."

export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"

STACK="AgentCore-LogAnalysisAgent-default"
CONFIG="agentcore/agentcore.json"
BACKUP="agentcore/agentcore.full.json.bak"
PHASE1="agentcore/agentcore.phase1.json"

echo "=== Phase 1 Deploy: Runtime + Memory only ==="

# Delete failed stack if present
STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$STATUS" == "ROLLBACK_COMPLETE" || "$STATUS" == "CREATE_FAILED" ]]; then
  echo "Deleting failed stack ($STATUS)..."
  aws cloudformation delete-stack --stack-name "$STACK" --region "$AWS_REGION"
  aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$AWS_REGION"
  echo "Stack deleted."
fi

# Backup full config, swap to phase1
if [ ! -f "$BACKUP" ]; then
  cp "$CONFIG" "$BACKUP"
  echo "Backed up full config to $BACKUP"
fi
cp "$PHASE1" "$CONFIG"
echo "Using phase1 config (runtime + short-term memory, no evaluators)"

# Deploy
npx agentcore deploy -y -v

echo ""
echo "=== Phase 1 complete ==="
echo "Test: npx agentcore invoke --session-id demo \"Analyze errors in the last hour\""
echo ""
echo "To restore full config (evaluators + online eval) after phase1 works:"
echo "  cp $BACKUP $CONFIG"
echo "  npx agentcore deploy -y -v"
