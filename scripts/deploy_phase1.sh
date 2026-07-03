#!/usr/bin/env bash
# Phase 1: Deploy runtime + short-term memory only (no evaluators).
# Prefer: bash scripts/fix_deploy.sh
set -euo pipefail
exec bash "$(dirname "$0")/fix_deploy.sh" phase1
