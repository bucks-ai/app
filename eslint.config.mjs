import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Autonomous runner Python venv (contains JS bundles that are not app code)
    "runner/langgraph/.venv/**",
    // M4b: cloned customer repos the runner checks out to execute business
    // missions (see .gitignore) — not bucks-ai source, must never be linted here
    "runner/langgraph/.workspaces/**",
  ]),
]);

export default eslintConfig;
