#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bash "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/20260701_跑商商誉迁移.py" "$@"
