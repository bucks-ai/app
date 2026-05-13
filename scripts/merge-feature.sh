#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || -z "${1:-}" ]]; then
  echo "Usage: ./scripts/merge-feature.sh feature/some-branch" >&2
  exit 1
fi

feature_branch="$1"

echo "pwd: $(pwd)"
echo "branch: $(git branch --show-current)"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree must be clean before merging. Current status:" >&2
  git status --short --branch >&2
  exit 1
fi

git switch main
git pull origin main
git merge --no-edit "${feature_branch}"

npm install
npm run lint
npm run build

git push origin main
git push deploy main

echo "Feature branch merged into main and pushed successfully."
