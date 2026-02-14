#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"

pytest tests/ -v --cov=gdscript_code_graph --cov-report=json:coverage.json "$@"
