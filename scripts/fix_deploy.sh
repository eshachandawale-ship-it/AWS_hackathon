#!/usr/bin/env bash
# Fix AgentCore CloudFormation deploy failures (NoStack / empty stack / ROLLBACK_COMPLETE).
#
# Root cause: full agentcore.json deploys runtime + 4 memory strategies + 3 evaluators
# + online eval in one stack — any single CREATE_FAILED rolls back everything.
#
# This script: clean failed stack → minimal phase1 deploy → verify deployed-state.json
#
# Usage (workshop):
#   export AWS_REGION=us-west-2
#   bash scripts/fix_deploy.sh
#   bash scripts/fix_deploy.sh --full   # after phase1 works, add evaluators incrementally

set -euo pipefail

cd "$(dirname "$0")/.."

export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"

STACK="AgentCore-LogAnalysisAgent-default"
MODE="${1:-phase1}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  AgentCore Deploy Fix — region: $AWS_REGION                  "
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── 1. AWS account in aws-targets.json ──────────────────────────────────────
echo "▶ Step 1/6: Configure aws-targets.json"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
if [[ ! "$ACCOUNT" =~ ^[0-9]{12}$ ]]; then
  echo "ERROR: Invalid AWS account ID: '$ACCOUNT'"
  exit 1
fi
cat > agentcore/aws-targets.json <<EOF
[
  {
    "name": "default",
    "description": "AWS Hackathon workshop environment",
    "account": "$ACCOUNT",
    "region": "$AWS_REGION"
  }
]
EOF
echo "   account=$ACCOUNT region=$AWS_REGION"
echo ""

# ── 2. CDK scaffold + deps ───────────────────────────────────────────────────
echo "▶ Step 2/6: Ensure agentcore/cdk is ready"
bash scripts/setup_cdk.sh
echo ""

# ── 3. Bedrock model access check ─────────────────────────────────────────────
echo "▶ Step 3/6: Check Bedrock model access (Claude Sonnet 4)"
MODEL="us.anthropic.claude-sonnet-4-20250514-v1:0"
if aws bedrock get-foundation-model --model-identifier "$MODEL" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "   ✓ $MODEL available"
else
  echo "   ✗ $MODEL NOT available in $AWS_REGION"
  echo "   → Open Bedrock console → Model access → enable Claude Sonnet 4"
  echo "   → Continuing anyway (runtime may fail if model not enabled)..."
fi
echo ""

# ── 4. Delete failed / rolled-back stack ─────────────────────────────────────
echo "▶ Step 4/6: Clean up failed CloudFormation stack"
STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo "NOT_FOUND")

echo "   Current stack status: $STATUS"

case "$STATUS" in
  NOT_FOUND)
    echo "   No existing stack — clean start"
    ;;
  CREATE_COMPLETE|UPDATE_COMPLETE)
    echo "   Stack already healthy — skipping delete"
    ;;
  DELETE_IN_PROGRESS)
    echo "   Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$AWS_REGION"
    ;;
  *)
    echo "   Deleting stack ($STATUS)..."
    aws cloudformation delete-stack --stack-name "$STACK" --region "$AWS_REGION"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$AWS_REGION"
    echo "   Stack deleted."
    ;;
esac
echo ""

# ── 5. Show last failure reason (if any events remain) ───────────────────────
echo "▶ Step 5/6: Previous failure summary (if available)"
aws cloudformation describe-stack-events \
  --stack-name "$STACK" \
  --region "$AWS_REGION" \
  --max-items 5 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table 2>/dev/null || echo "   (no previous events — stack was cleaned)"
echo ""

# ── 6. Deploy ─────────────────────────────────────────────────────────────────
CONFIG="agentcore/agentcore.json"
BACKUP="agentcore/agentcore.full.json.bak"
PHASE1="agentcore/agentcore.phase1.json"
PHASE2="agentcore/agentcore.phase2.json"
FULL="agentcore/agentcore.full.json"

echo "▶ Step 6/6: Deploy (mode: $MODE)"

if [ ! -f "$BACKUP" ] && [ -f "$CONFIG" ]; then
  cp "$CONFIG" "$BACKUP"
  echo "   Backed up config → $BACKUP"
fi

case "$MODE" in
  phase1|*)
    cp "$PHASE1" "$CONFIG"
    echo "   Using phase1: runtime + short-term memory only"
    ;;
  phase2)
    cp "$PHASE2" "$CONFIG"
    echo "   Using phase2: runtime + LTM memory + evaluators (no online eval)"
    ;;
  full)
    if [ -f "$FULL" ]; then
      cp "$FULL" "$CONFIG"
    elif [ -f "$BACKUP" ]; then
      cp "$BACKUP" "$CONFIG"
    fi
    echo "   Using full config (online eval enableOnCreate=false)"
    ;;
esac

echo ""
echo "   Running: npx agentcore deploy -y -v"
echo "   (this takes 3-8 minutes)"
echo ""

if npx agentcore deploy -y -v; then
  echo ""
  if [ -f "agentcore/.cli/deployed-state.json" ]; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  ✓ DEPLOY SUCCESS                                            ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Test invoke:"
    echo '  npx agentcore invoke --session-id demo "Identify the single primary root cause from the last 2 hours"'
    echo ""
    if [ "$MODE" = "phase1" ]; then
      echo "Next: add memory + evaluators incrementally:"
      echo "  bash scripts/fix_deploy.sh phase2"
    elif [ "$MODE" = "phase2" ]; then
      echo "Next: add online eval:"
      echo "  bash scripts/fix_deploy.sh full"
    fi
  else
    echo "WARNING: deploy reported success but deployed-state.json missing"
    echo "Check: ls -la agentcore/.cli/"
  fi
else
  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  ✗ DEPLOY FAILED — run diagnostics                           ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
  bash scripts/diagnose_deploy.sh
  exit 1
fi
