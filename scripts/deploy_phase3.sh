#!/usr/bin/env bash
# Phase 3: Full config with online eval (enableOnCreate=false).
set -euo pipefail
exec bash "$(dirname "$0")/fix_deploy.sh" full
