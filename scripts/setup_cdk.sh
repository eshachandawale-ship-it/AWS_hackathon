#!/usr/bin/env bash
# Generate agentcore/cdk if missing (required for agentcore deploy).
# Run from project root: bash scripts/setup_cdk.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CDK_DIR="$PROJECT_ROOT/agentcore/cdk"

if [ -d "$CDK_DIR" ] && [ -f "$CDK_DIR/package.json" ]; then
  echo "agentcore/cdk already exists."
else
  echo "Generating agentcore/cdk scaffold..."
  TMP_DIR=$(mktemp -d)
  npx agentcore create \
    --name LogAnalysisAgent \
    --no-agent \
    --skip-git \
    --skip-install \
    --skip-python-setup \
    --output-dir "$TMP_DIR"

  mkdir -p "$PROJECT_ROOT/agentcore"
  cp -r "$TMP_DIR/LogAnalysisAgent/agentcore/cdk" "$CDK_DIR"
  rm -rf "$TMP_DIR"
  echo "Created $CDK_DIR"
fi

echo "Installing CDK dependencies..."
cd "$CDK_DIR"
npm install
echo "Done. Run: npx agentcore deploy -y"
