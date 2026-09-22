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
    // Python virtualenvs ship vendored JS (torch, sklearn) that is not ours
    // to lint; without this `eslint .` reports ~75 findings from site-packages.
    "**/.venv/**",
    "backend/prisma/**",
  ]),
]);

export default eslintConfig;
