#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || -z "${1:-}" ]]; then
  echo "Usage: ./scripts/finish-feature.sh \"Commit message\"" >&2
  exit 1
fi

commit_message="$1"
current_branch="$(git branch --show-current)"

echo "pwd: $(pwd)"
echo "branch: ${current_branch}"

if [[ "${current_branch}" == "main" ]]; then
  echo "Refusing to finish a feature from main." >&2
  exit 1
fi

git status --short --branch

npm install
npm run lint
npm run build

git add .

if git diff --cached --quiet; then
  echo "Nothing to commit; continuing to push current branch."
else
  git commit -m "${commit_message}"
fi

git push -u origin HEAD

echo "Feature branch finished and pushed successfully."
