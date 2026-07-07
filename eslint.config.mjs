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
    // Installed AI skills (bundled scripts are not app code)
    ".claude/**",
  ]),
]);

export default eslintConfig;
