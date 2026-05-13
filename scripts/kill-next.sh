#!/usr/bin/env bash
set -euo pipefail

echo "Running Next dev processes:"
if ! pgrep -afil "next dev"; then
  echo "No Next dev processes found."
  exit 0
fi

echo
read -r -p "Kill these Next dev processes? Type 'yes' to confirm: " confirmation

if [[ "${confirmation}" != "yes" ]]; then
  echo "Cancelled. No processes were killed."
  exit 0
fi

pkill -f "next dev"

echo "Next dev processes killed."
