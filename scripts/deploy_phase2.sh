#!/usr/bin/env bash
# Phase 2: Add LTM memory + evaluators (no online eval).
# Run after phase1 succeeds.
set -euo pipefail
exec bash "$(dirname "$0")/fix_deploy.sh" phase2
