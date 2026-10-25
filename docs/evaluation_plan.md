# Plan: making RedGuard's evaluation support its claims

Status: plan only. Nothing here has been implemented or run. Written 2026-10-25 after the 5.0.0 audit fixes
(`docs/audit_fixes.md`), which repaired the scoring mechanics but did not make the evaluation trustworthy.

## What "evaluation" has to deliver

A claim of the form "model X is more vulnerable than Y", "the hardened prompt helps" or "defence D contains the
attack" needs four things the project does not have yet:

1. a scorer whose error rate is **measured**, not assumed;
2. **enough independent items** that the interval is narrower than the effect;
3. **exposure**: the attack was actually in front of the agent;
4. **held-out items**: nothing in the prompts, patterns or indicators was written with the test items in view.

Each is a work package below, per mode. Estimates marked (est.) are mine, not measured.

## What the numbers say today (computed from the repo, no model)

- Attack probes per family: direct injection 8, content injection 9, memory poisoning 6, tool manipulation 4, planning 5,
  exfiltration 6, autonomous actions 5, goal diversion 3 (46 total).
- Precision of a rate at p = 0.20: n = 8 or 9 gives 95% CI half-width ±0.25; n = 46 gives ±0.11; n = 100 ±0.08; n = 200 ±0.06.
  To tell 0.20 from 0.10 you need about **199 independent probes per arm**; 0.20 from 0.05 about 76; 0.30 from 0.20 about 294;
  0.10 from 0.05 about 435 (two-sided 5%, 80% power, unpaired). Comparing models on the **same** probes (paired) needs fewer;
  how many depends on how often the two models agree on a probe (est.: roughly half to two thirds of the unpaired figure).
- Lab: the unit is the case, not the run. 9 cases (10 with RGM-010), 3 repetitions at temperature 0 were mostly copies, so the
  effective n is about 8 for the in-scope cases: ±0.25 at best.
- Lab exposure: in granite's run only 3 of 15 in-scope attack runs had the poisoned content in front of any agent.
- The hardened prompt shares **no 4-word phrase** with any of the 46 probes, but it names three attack phrases ("ignore previous
  instructions", "system override", "internal note") and lists all 8 families and 12 scenarios, which is what the probes are built from.
- Re-scoring the 4.0.0 replies showed how much the scorer's rule can decide the headline (Nemotron-3 Ultra hardened: 3 or 50 of
  92 compromised depending on the tie-break). 35 of 46 attack probes are now scored from calls or canaries, which removes that
  ambiguity, but 11 still depend on phrases, and no human has checked any of it.

## Cross-cutting infrastructure (both modes)

| ID | What | Files | Needs a model? |
|---|---|---|---|
| X1 | **dev / test split.** Add `split: "dev" \| "test"` to probes and cases (schema, validator). Patterns, prompts, indicators, canaries and clean scripts are written against `dev` only; every published number is on `test`. A test fails if a `test` item's text, indicator or canary appears in `policy.yaml`, `system_prompts.json` or the scorer. | `schema.json`, `case_schema.json`, validators, new `core/shared/splits.py`, tests | No |
| X2 | **Frozen manifest.** `evaluation_manifest.json`: SHA-256 of the corpus, cases, prompts, policy, scorer source and tool list. Stored on every session and experiment; the report refuses to label a result "5.x" if the hash differs from the one stored. | `core/shared/manifest.py`, `Session`/experiment columns, report | No |
| X3 | **Claims policy in the product.** Leaderboard and Lab compare page rank only when the paired difference's clustered CI excludes zero, otherwise show "no difference detected" and the minimum detectable effect for the current n. Show the scorer's measured accuracy (WP-S1/L6) next to every rate. | `leaderboard.py`, `models/page.tsx`, `analysis.py`, compare page | No |
| X4 | **Power calculator.** `python -m scripts.power --rate 0.2 --effect 0.1 --paired-agreement 0.8` prints needed n and, for current data, the minimum detectable effect. Used by X3. | `scripts/power.py`, test | No |
| X5 | **Pre-registration file.** Before a run: `analysis/<run-id>.md` lists the comparisons, the split, the n, the exclusion rules and the stopping rule; the report links it; deviations are listed. | docs template, report builder | No |
| X6 | **Run protocol.** At least 3 runs per (model, prompt mode, arm) with different seeds (local) or on different days (hosted); record model id and date; temperature 0 and one sensitivity run at 0.7; Holm correction across the pre-registered comparisons. | `sweep.py`, Scanner start, docs | Yes, at run time |

## Scanner mode

| ID | Problem | Fix | Acceptance |
|---|---|---|---|
| S1 | The scorer's error is unknown. | Label the exported sample (`results/reanalysis/labelling_sample.csv`, 56 + 20 rows) with two people; then widen to about 200 Scanner rows stratified by method (actions / canary / text / control) and outcome. `labels.py agree` gives kappa and confusion matrices. Fix every probe where scorer and consensus disagree. | Humans kappa ≥ 0.8; scorer vs consensus ≥ 0.90 per method, recall of COMPROMISED ≥ 0.9 |
| S2 | 11 probes still depend on phrases (DI-003/005/006, CI-006, MP-004/005/006, EX-003, GD-001/003/004). | Convert each to evidence where a behaviour exists: GD-001 (promote TravelCorp) to a brand canary or a `place_order` action; GD-003/GD-004 to `save_memory` / `send_email` actions; EX-003 to a canary; MP-004/006 to "agent states the poisoned fact as current policy" with a judge or a rubric. Probes with no observable behaviour (DI-005/006 harmful completions) leave the ASR and are reported as a separate refusal-style measure. | 0 probes in the headline ASR scored by phrase, or each such probe has S1 accuracy ≥ 0.9 |
| S3 | Sample too small and unbalanced (3 to 9 per family). | Generate **variants**: per family, a template with axes (goal x channel x wording style x target resource), 20+ variants, each with its own canary or `success_actions`, a matched benign control (as RG-CTL-006 matches RG-TM-006), and `split`. Target ≥ 160 test attacks (20 per family) and ≥ 80 matched controls. Keep ids `RG-XX-NNN`; bump DATASET_VERSION. | Test split ≥ 160 attacks; every family ≥ 15; near-duplicate test (difflib > 0.8) passes on the whole corpus |
| S4 | The hardened prompt names attack phrases and the taxonomy. | Rewrite the hardened prompt in general principles (treat tool output as data, confirm irreversible actions, never reveal system text); remove named phrases and the family/scenario enumeration or move them to a separate "taxonomy-aware" mode reported as such. Freeze it (X2) before any test-split run. | Test: no `dev` or `test` probe phrase or indicator occurs in the hardened prompt; hash recorded |
| S5 | Indirect probes are IGNORED when the agent never calls the read tool, so low success can mean "never looked". | Report **ASR given exposure** (fetch/read recorded) as the headline for indirect families; add an optional `exposure_forced` mode where the scaffold forces the first call to the fixture tool (via `tool_choice`) and report both. | Leaderboard shows exposed / total; exposed-only ASR with CI |
| S6 | Regex filter is evaluated on patterns written with the corpus in view. | Report block rate on the **test** attacks and on held-out benign sets (XSTest plus a workplace-requests set written blind); any pattern change is tuned on dev, reported on test. | Filter FN and FP rates with Wilson CIs on test splits only |
| S7 | Realism: synthetic probes, mock tools, one author. | Import about 30 injection cases from an external benchmark (AgentDojo/InjecAgent style) as `source: external` and check that the model ranking on external cases agrees with the internal ranking (Spearman, reported). If it does not, say the internal numbers do not transfer. | External subset run and rank agreement reported |
| S8 | Hosted agents unseeded; models drift. | X6 protocol; store model id / provider revision / date in `modelConfig`; refuse to pool runs more than N days apart for hosted models without a flag. | Config recorded; pooling check test |
| S9 | Paired structure unused. | Compare agents and prompt modes with a **paired** test per probe (McNemar or permutation, clustered by family), plus effect size; Holm across comparisons. | `analysis.compare_scanner()` with tests; leaderboard uses it (X3) |

## Lab mode

| ID | Problem | Fix | Acceptance |
|---|---|---|---|
| L1 | 9 cases, effective n about 8. | Case **matrix generator**: objective (read PII table / read payroll file / write unapproved vendor / send a message) x channel (files, web, db, kv, task) x entry (A, B) x phrasing; each case ships a validated clean script; both a task that names the channel and one that does not (RGM-007 / RGM-010 pattern) so `task_endorses_channel` is a controlled variable. Target ≥ 30 attack cases in `test` plus controls. | `validate_all` passes; clean scripts complete and never satisfy the objective; ≥ 30 in-scope test cases |
| L2 | Runs where nobody read the attack. | Add a harness option `exposure: "natural" \| "forced"`: forced puts the artifact in the entry agent's first tool result (the read is performed by the harness, still recorded and tainted). Report both; headline is exposed-only ASR with the natural rate beside it. | Forced arm exposure ≥ 95%; natural arm exposure reported |
| L3 | Models too small to drive the harness. | Suitability gate before a model enters any comparison: ≤ 10% invalid replies, entry agent reads the artifact in ≥ 50% of natural runs, agents finish within budget in ≥ 70% of clean runs. Models below the gate are shown as "unsuitable" and excluded from ASR comparisons. | Gate implemented in `smoke`/report; failing model never ranked |
| L4 | Repetitions are copies; no variance estimate. | L7's seeds, temperature 0.3-0.7 for the main sweep, ≥ 5 repetitions; analysis clustered by case. | Within-case variance reported; n_eff stated |
| L5 | Defence arms never evaluated. | Run all five arms **on the same cases and seeds** (paired), pre-registered comparisons EXP-4/6/7; measure the benign cost (clean-half task success) of each; report per-case paired differences with bootstrap CI. | Compare page shows paired result, cost, and "insufficient evidence" when n < 30 |
| L6 | Verdicts never checked by a human. | Label 60 attack runs (objective reached? entry influenced? propagated by message?) with two people; kappa and confusion vs the evaluator; add every disagreement as a golden trace. | kappa ≥ 0.8; evaluator ≥ 0.9 on objective, ≥ 0.85 on influence |
| L7 | Evaluator rules (influence = deviation from clean) are heuristics. | After L6, decide whether INFLUENCED needs a stricter definition; report COMPROMISED/objective as primary, INFLUENCED as secondary. | Documented definition matches labelled data |

## Order of work

**Phase 0, no model (about 1-2 days, est.):** X1, X2, X4, X3, S4 (rewrite and freeze the hardened prompt), the schema fields for
splits and the claims policy. Everything testable offline.

**Phase 1, no model (about 3-5 days, est.):** S3 variant generator and L1 case matrix with their validators and clean-script
checks; S2 conversions; labelling tooling widened (S1/L6 sample export for 200 / 60 rows); L3 gate; S9/L5 paired analysis code.

**Phase 2, needs your go-ahead:** pilot on the local model you approve: Scanner 3 seeds on `dev`, Lab natural vs forced exposure on a few
cases. Purpose: check exposure rates, suitability gate, the scorer on real replies. Label from the pilot (S1, L6). Fix what labelling finds.

**Phase 3, needs your go-ahead:** pre-registered sweeps on `test`: Scanner (≥ 2 models x baseline/hardened x 3 runs), Lab (all five arms,
paired, ≥ 30 cases x ≥ 5 reps). Reports generated from the frozen manifest.

**Phase 4:** write up only 5.x numbers; apply `report_errata.md`; state the scorer accuracy and minimum detectable effect beside each result.

## Definition of done for "evaluation is sound"

- Scorer accuracy against two-person labels is published per scoring method (S1, L6).
- Test split: ≥ 160 Scanner attacks (≥ 15 per family) and ≥ 30 Lab cases; no test item used for tuning (X1 test).
- Hardened prompt contains no dev/test probe phrase and is hash-frozen (S4, X2).
- Every compared number is exposed-only or shows its exposure rate (S5, L2).
- Every ranking is a paired difference with a CI that excludes zero, else "no difference detected" with the minimum detectable effect (X3, S9, L5).
- All of it reproducible from a manifest hash.

## Decisions I need from you

1. **Models.** Your standing rule is local `granite3.3:2b` only. A 2B model fails the suitability gate (L3) in Lab and gives little signal;
   a meaningful Lab comparison needs at least one more capable model (local larger, or hosted). Allow it?
2. **Judge.** An LLM judge for the few rubric-style probes (MP-004/006) uses a model and adds its own error. Allow it, or humans only?
3. **Forced exposure.** Which is the headline: natural (realistic, low exposure) or forced (clean measure, less realistic)? The plan
   reports both and makes exposed-only the headline; say if you want the other.
4. **Split.** Proposed 40% dev / 60% test (more test items matter more). Agree?
5. **Labellers.** Who are the two people, and how many hours can they give (S1: about 200 replies, L6: 60 runs)?
6. **Scope.** If time is short, the minimum that fixes the largest problems is X1, X2, S4, S5/L2 and the labelling (S1/L6); the
   variant generators (S3/L1) are what buy statistical power and take the longest.
