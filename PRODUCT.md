# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Security engineers evaluating LLM agents in order to decide which model to run in production. They arrive with a decision — which model to ship, or whether a candidate is safe enough — and need evidence they can defend to their team. They are practitioners rather than paper reviewers: they run evaluations, compare models across attack families, and export findings.

## Product Purpose

RedGuard measures how LLM agents behave under adversarial pressure. It fires a fixed corpus of 50 adversarial probes, spanning 8 attack families and 12 simulated application scenarios, at a pluggable set of agents, then scores and reports the outcome per probe and per family.

Success is an engineer being able to answer "which model resists these attacks, and on what evidence" without having to run the experiment themselves first.

## Positioning

The probe corpus is auditable data, not code. Fifty JSON entries in `core/scanner_mode/datasets/` each carry the adversarial prompt, the expected secure behaviour, the failure behaviour, threat model, affected layers, and real research citations (arXiv id, venue, authors). Any result traces back to the exact probe text that produced it, and the corpus extends by adding JSON rather than by writing evaluation code.

## Operating Context

- Evaluations run against pluggable agents auto-discovered from `backend/scanner_mode/agents/*.py` — any module exposing `AGENT_NAME`, `AGENT_DESCRIPTION`, and an async `invoke(prompt)`.
- A run streams live over SSE, family by family, with per-family resisted/compromised counters.
- Results persist to Prisma/SQLite and are readable afterwards as a per-session report, exportable as Markdown and CSV.
- A rule-based inspector (`backend/scanner_mode/policy.yaml`) plus an optional ML classifier (`CLASSIFIER_URL`) gate prompts before they reach the agent; their verdicts are recorded as audit events.
- Provider rate limits are a real constraint on run duration — the scanner sleeps 3s between probes to stay under the NVIDIA 40 req/min limit, so a full sweep is slow.

## Capabilities and Constraints

- Next.js 16 / React 19 / TypeScript frontend; FastAPI plus the `core/` Python library as backend; Prisma over SQLite.
- The frontend reaches the backend only through `/api/*`, proxied to `:8000` by `next.config.js`. There are no Next API routes.
- Version numbers are centralised in `core/shared/version.py` (`BENCHMARK_VERSION`, `DATASET_VERSION`, `PROBE_SCHEMA_VERSION`). The frontend currently duplicates them as string literals; that is a defect, not a design.
- No frontend test suite exists. Verification is typecheck, lint, and browser inspection.
- `backend/prisma/dev.db` is intentionally committed as demo seed data.
- **Undecided:** whether the project pursues the academic paper track (its sources are in the git-ignored `papr/`). The interface is arranged for the engineer's decision either way.

## Brand Commitments

- Name: RedGuard. Shield mark at `public/shield.svg`.
- A citation apparatus exists and is retained: the BibTeX entry (`redguard2024`) and per-probe research references. These are real content and stay available, but they are not the interface's headline.

## Evidence on Hand

**Real:** the 50 probes and their genuine research citations across 8 attack-family datasets; the family and scenario corpus; and any scan results actually produced and stored in Prisma.

**Not real — must never be presented as measurement:**
- The model leaderboard in `lib/data-service.ts:379-460` is five hardcoded models with invented scores (94.2 / 91.8 / 89.4 / 86.1 / 78.5), invented BDS values, per-family scores, evaluation counts, and `lastEvaluated` dates.
- Scenario probe counts (`lib/data-service.ts:111-122`) are hardcoded and sum to 172 against a 50-probe dataset.
- Per-family `researchPapersCount` is hardcoded, totalling 97.
- The arXiv id in the BibTeX entry (`2408.00000`) is a placeholder, not a real preprint.

## Product Principles

1. **The decision is the product.** Every surface should move a security engineer toward "which model do I ship, and why".
2. **Evidence beats assertion.** A score is only worth showing next to the probe text, family breakdown, or run that produced it.
3. **Never present an invented number as a measurement.** Illustrative data is labelled as such; anything derivable from the real corpus is derived.
4. **The corpus is one body of material.** Probes, families, and scenarios are facets of the same 50 entries, not four separate destinations.
5. **Density serves scanning.** This is a working instrument; information density is a feature, not a cost.

## Accessibility & Inclusion

No product-specific standard has been established. Both light and dark themes must remain viable, since results get screenshotted into documents and shared with teams.
