#!/usr/bin/env bash
# Diagnose AgentCore deploy failures — run from project root
set -euo pipefail

REGION="${AWS_REGION:-us-west-2}"
STACK="AgentCore-LogAnalysisAgent-default"

echo "=== AgentCore Deploy Diagnostics ==="
echo "Region: $REGION"
echo "Stack:  $STACK"
echo ""

echo "--- AWS Identity ---"
aws sts get-caller-identity --region "$REGION" 2>&1 || true
echo ""

echo "--- Stack Status ---"
aws cloudformation describe-stacks \
  --stack-name "$STACK" \
  --region "$REGION" \
  --query 'Stacks[0].[StackStatus,StackStatusReason]' \
  --output text 2>&1 || echo "Stack not found (may have been deleted after rollback)"
echo ""

echo "--- FAILED Resources (root cause) ---"
aws cloudformation describe-stack-events \
  --stack-name "$STACK" \
  --region "$REGION" \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[Timestamp,LogicalResourceId,ResourceType,ResourceStatusReason]' \
  --output table 2>&1 || echo "No events (stack may not exist)"
echo ""

echo "--- Recent Stack Events (last 15) ---"
aws cloudformation describe-stack-events \
  --stack-name "$STACK" \
  --region "$REGION" \
  --max-items 15 \
  --query 'StackEvents[].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
  --output table 2>&1 || true
echo ""

echo "--- Latest Deploy Log ---"
LATEST=$(ls -t agentcore/.cli/logs/deploy/deploy-*.log 2>/dev/null | head -1 || true)
if [ -n "$LATEST" ]; then
  echo "File: $LATEST"
  tail -30 "$LATEST"
else
  echo "No deploy logs found"
fi
echo ""

echo "--- Bedrock Model Access (Sonnet 4) ---"
aws bedrock list-foundation-models \
  --region "$REGION" \
  --query "modelSummaries[?contains(modelId,'claude-sonnet-4')].modelId" \
  --output table 2>&1 || echo "Cannot list models — check Bedrock permissions"
echo ""

echo "=== Recommended next steps ==="
echo "1. Run the automated fix (deletes failed stack + phased deploy):"
echo "   bash scripts/fix_deploy.sh"
echo ""
echo "2. If phase1 works, add memory + evaluators:"
echo "   bash scripts/fix_deploy.sh phase2"
echo ""
echo "3. Then add online eval:"
echo "   bash scripts/fix_deploy.sh full"
echo ""
echo "4. Enable Claude Sonnet 4 in Bedrock console (region: $REGION)"
