#!/usr/bin/env bash
# Full-stack demo script for AWS hackathon environment.
# Run from project root after: aws configure, npm i -g @aws/agentcore, pip install uv

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION="$REGION"

echo "=============================================="
echo " Log Analysis Agent — Full Stack Demo"
echo "=============================================="

# ── 0. Prerequisites check ─────────────────────
echo ""
echo "[0/7] Checking prerequisites..."
command -v agentcore >/dev/null || { echo "Install: npm install -g @aws/agentcore"; exit 1; }
command -v aws >/dev/null || { echo "AWS CLI required"; exit 1; }
command -v python3 >/dev/null || { echo "Python 3.12+ required"; exit 1; }
aws sts get-caller-identity

# ── 1. Seed synthetic logs ─────────────────────
echo ""
echo "[1/7] Seeding synthetic CloudWatch logs..."
pip install -q boto3
python3 scripts/seed_cloudwatch_logs.py --generate --region "$REGION"

# ── 2. Deploy AgentCore resources ──────────────
echo ""
echo "[2/7] Deploying Runtime + Memory + Evaluators + Online Eval..."
agentcore deploy -y

# ── 3. Verify deployment status ────────────────
echo ""
echo "[3/7] Deployment status..."
agentcore status

# ── 4. Runtime demo — basic analysis ───────────
echo ""
echo "[4/7] Runtime demo — log analysis..."
agentcore invoke --session-id demo-hackathon \
  "Analyze all errors in /hackathon/log-analysis/ecommerce-platform from the last 2 hours. Rank by severity."

# ── 5. Memory demo — multi-turn ────────────────
echo ""
echo "[5/7] Memory demo — follow-up (same session)..."
agentcore invoke --session-id demo-hackathon \
  "Based on our earlier analysis, which service should we investigate first and why?"

agentcore invoke --session-id demo-hackathon \
  "Remember that I only care about CRITICAL and HIGH severity issues going forward."

# ── 6. Corner case demos ───────────────────────
echo ""
echo "[6/7] Corner case demos..."
echo "  → Empty prompt:"
agentcore invoke "" 2>/dev/null || true

echo "  → Non-existent log group:"
agentcore invoke --session-id demo-corner \
  "Analyze errors in /nonexistent/log-group from the last hour"

# ── 7. Observability + Evaluations ─────────────
echo ""
echo "[7/7] Observability & Evaluations..."
echo "  → Stream runtime logs (Ctrl+C to stop):"
echo "    agentcore logs --follow"
echo ""
echo "  → List traces:"
agentcore traces list --limit 5 2>/dev/null || echo "    (traces appear 2-5 min after invocations)"
echo ""
echo "  → On-demand evaluation (wait 5-10 min after invocations for traces):"
echo "    agentcore run eval --runtime LogAnalysisAgent --evaluator LogAnalysisSessionQuality --days 1"
echo "    agentcore run eval --runtime LogAnalysisAgent --evaluator LogAnalysisTraceAccuracy --days 1"
echo "    agentcore run eval --runtime LogAnalysisAgent --evaluator CloudWatchToolUsage --days 1"
echo ""
echo "  → Online eval logs:"
echo "    agentcore logs evals --runtime LogAnalysisAgent --since 1h"
echo ""
echo "  → CloudWatch GenAI Observability:"
echo "    Console → CloudWatch → GenAI Observability → AgentCore tab"
echo ""
echo "=============================================="
echo " Demo complete! See docs/DEMO_GUIDE.md"
echo "=============================================="
