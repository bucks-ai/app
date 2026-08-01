#!/usr/bin/env bash
# Run Lighthouse against a route and write JSON + HTML reports.
#
#   ./scripts/lighthouse.sh /                  # against http://localhost:3000
#   ./scripts/lighthouse.sh /intake 3001       # against a different port
#   ./scripts/lighthouse.sh https://bucks.ai/  # against a full URL
#
# Performance scores from `next dev` are meaningless — the dev build is
# unminified, unsplit, and recompiles on request. For real numbers:
#   npm run build && npm start   (then point this at port 3000)
# Accessibility, SEO, and best-practices scores are usable either way.

set -euo pipefail

TARGET="${1:-/}"
PORT="${2:-3000}"
OUT_DIR=".claude/qa-reports/lighthouse"

if [[ "$TARGET" == http://* || "$TARGET" == https://* ]]; then
  URL="$TARGET"
else
  URL="http://localhost:${PORT}${TARGET}"
fi

if ! curl -sSf -o /dev/null --max-time 10 "$URL"; then
  echo "Cannot reach $URL — start the server first (npm run dev, or npm run build && npm start)." >&2
  exit 1
fi

if [[ "$URL" == http://localhost:* ]] && ! pgrep -f "next start" >/dev/null 2>&1; then
  echo "note: this looks like a dev server. Treat the performance score as noise; the other three categories are still valid." >&2
fi

mkdir -p "$OUT_DIR"
SLUG=$(echo "$TARGET" | sed 's#^https\?://##; s#[^a-zA-Z0-9]#_#g; s#^_*##; s#_*$##')
SLUG="${SLUG:-root}"
STAMP=$(date +%Y%m%d-%H%M%S)
BASE="${OUT_DIR}/${SLUG}-${STAMP}"

echo "Auditing $URL"
npx --yes lighthouse@latest "$URL" \
  --quiet \
  --chrome-flags="--headless=new --no-sandbox" \
  --output=json --output=html \
  --output-path="${BASE}" \
  --only-categories=performance,accessibility,best-practices,seo

# Lighthouse appends .report.json / .report.html to --output-path.
JSON="${BASE}.report.json"

if [[ ! -f "$JSON" ]]; then
  echo "Lighthouse produced no JSON report at $JSON" >&2
  exit 1
fi

echo ""
echo "Scores for $URL"
node -e '
const path = require("path");
const r = require(path.resolve(process.argv[1]));

for (const c of Object.values(r.categories)) {
  const score = c.score === null ? "  ?" : String(Math.round(c.score * 100)).padStart(3);
  console.log(`  ${score}  ${c.title}`);
}

const m = r.audits;
console.log("");
for (const id of ["first-contentful-paint", "largest-contentful-paint", "total-blocking-time", "cumulative-layout-shift", "speed-index"]) {
  if (m[id] && m[id].displayValue) console.log(`  ${m[id].title}: ${m[id].displayValue}`);
}

const fails = Object.values(m)
  .filter((a) => a.score !== null && a.score < 0.9 && a.scoreDisplayMode !== "informative")
  .sort((a, b) => a.score - b.score);
console.log(`\n  ${fails.length} audits below 90:`);
for (const a of fails.slice(0, 15)) console.log(`   - [${Math.round(a.score * 100)}] ${a.title}`);
if (fails.length > 15) console.log(`   … and ${fails.length - 15} more — see the HTML report`);
' "$JSON"

echo ""
echo "JSON: $JSON"
echo "HTML: ${BASE}.report.html"
