#!/usr/bin/env bash
set -euo pipefail
# Codespaces may carry a Git LFS pre-push hook into this Python image.
# Supply its official Debian package instead of removing or bypassing the hook.
if ! command -v git-lfs >/dev/null 2>&1; then
  # Refresh the signed Debian source without unrelated optional repositories.
  if [[ -f /etc/apt/sources.list.d/debian.sources ]]; then
    sudo apt-get update -qq \
      -o Dir::Etc::sourcelist="sources.list.d/debian.sources" \
      -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"
  else
    sudo apt-get update -qq
  fi
  sudo apt-get install -y --no-install-recommends git-lfs
fi
python -m pip install --disable-pip-version-check 'uv==0.13.8'
uv sync --locked
uv run l1-lab doctor
