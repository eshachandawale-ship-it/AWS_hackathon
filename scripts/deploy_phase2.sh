#!/usr/bin/env bash
# Phase 2: Restore full config (evaluators + online eval) after phase1 succeeds.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP="agentcore/agentcore.full.json.bak"
CONFIG="agentcore/agentcore.json"

if [ ! -f "$BACKUP" ]; then
  echo "No backup found at $BACKUP — run deploy_phase1.sh first"
  exit 1
fi

cp "$BACKUP" "$CONFIG"
echo "Restored full agentcore.json"

export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"

npx agentcore deploy -y -v

echo "=== Full deploy complete ==="
echo "Run evals after 5-10 min: npx agentcore run eval --runtime LogAnalysisAgent --evaluator LogAnalysisSessionQuality --days 1"
