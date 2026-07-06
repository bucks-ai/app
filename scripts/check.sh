#!/usr/bin/env bash
set -euo pipefail

echo "pwd: $(pwd)"
echo "branch: $(git branch --show-current)"

npm ci
npm run lint
npx next typegen
npx tsc --noEmit
npm test
npm run build

echo "Project verification completed successfully."
