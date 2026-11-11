#!/usr/bin/env bash

# Exit immediately if something fails
set -e

./.venv-linux/bin/python ./main.py "$@"
