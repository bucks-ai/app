#!/usr/bin/env bash
set -euo pipefail

folders=(
  "$HOME/bucks-ai"
  "$HOME/bucks-ai-auth"
  "$HOME/bucks-ai-persistence"
  "$HOME/bucks-ai-tool-backend"
  "$HOME/bucks-ai-tool-ui"
  "$HOME/bucks-ai-github-backend"
  "$HOME/bucks-ai-github-ui"
)

for folder in "${folders[@]}"; do
  if [[ -d "${folder}" ]]; then
    echo
    echo "== ${folder} =="
    git -C "${folder}" status --short --branch
  fi
done
