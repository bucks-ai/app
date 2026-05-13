#!/usr/bin/env bash
set -euo pipefail

echo "pwd: $(pwd)"
echo "branch: $(git branch --show-current)"

npm install
npm run lint
npm run build

echo "Project verification completed successfully."
