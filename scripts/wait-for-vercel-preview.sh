#!/usr/bin/env bash
# Polls the Vercel API for a preview deployment matching $COMMIT_SHA and
# writes `found` / `url` to $GITHUB_OUTPUT. Never exits non-zero — a missing
# token, missing project id, unmatched deployment, or timeout are all treated
# as "no preview" so the calling job can skip gracefully instead of failing.
set -uo pipefail

TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-600}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-15}"

skip() {
  echo "::notice::${1}"
  echo "found=false" >>"$GITHUB_OUTPUT"
  echo "url=" >>"$GITHUB_OUTPUT"
  exit 0
}

if [[ -z "${VERCEL_TOKEN:-}" || -z "${VERCEL_PROJECT_ID:-}" ]]; then
  skip "VERCEL_TOKEN or VERCEL_PROJECT_ID not set — skipping preview E2E."
fi

if [[ -z "${COMMIT_SHA:-}" ]]; then
  skip "No commit SHA to resolve a preview deployment for — skipping preview E2E."
fi

deadline=$((SECONDS + TIMEOUT_SECONDS))

while true; do
  response="$(curl -sf \
    -H "Authorization: Bearer ${VERCEL_TOKEN}" \
    "https://api.vercel.com/v6/deployments?projectId=${VERCEL_PROJECT_ID}&sha=${COMMIT_SHA}&limit=5" || true)"

  if [[ -n "${response}" ]]; then
    deployment="$(echo "${response}" | jq -c '.deployments[0] // empty')"

    if [[ -n "${deployment}" ]]; then
      state="$(echo "${deployment}" | jq -r '.readyState // .state // empty')"
      url="$(echo "${deployment}" | jq -r '.url // empty')"

      case "${state}" in
        READY)
          echo "found=true" >>"$GITHUB_OUTPUT"
          echo "url=https://${url}" >>"$GITHUB_OUTPUT"
          echo "::notice::Resolved Vercel preview deployment: https://${url}"
          exit 0
          ;;
        ERROR | CANCELED | BLOCKED | DELETED)
          skip "Vercel preview deployment ended in state ${state} — skipping preview E2E."
          ;;
      esac
    fi
  fi

  if (( SECONDS >= deadline )); then
    skip "Timed out waiting for a ready Vercel preview deployment — skipping preview E2E."
  fi

  sleep "${POLL_INTERVAL_SECONDS}"
done
