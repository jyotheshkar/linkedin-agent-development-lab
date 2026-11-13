#!/usr/bin/env bash
set -euo pipefail
python -m pip install --disable-pip-version-check 'uv==0.13.8'
uv sync --locked
uv run l1-lab doctor
