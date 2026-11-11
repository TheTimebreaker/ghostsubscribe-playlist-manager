#!/usr/bin/env bash

# Exit immediately if something fails
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/.venv-linux/bin/python" "$SCRIPT_DIR/src/launcher.py" "$@"
