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
  // Scanner mode and Lab mode never import each other (docs/architecture.md);
  // shared/ may use either.
  {
    files: ["app/(scanner_mode)/**", "components/scanner_mode/**", "lib/scanner_mode/**"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [{ group: ["**/lab_mode/**"], message: "Scanner mode must not import Lab mode." }] }],
    },
  },
  {
    files: ["app/(lab_mode)/**", "components/lab_mode/**", "lib/lab_mode/**"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [{ group: ["**/scanner_mode/**"], message: "Lab mode must not import Scanner mode." }] }],
    },
  },
]);

export default eslintConfig;
