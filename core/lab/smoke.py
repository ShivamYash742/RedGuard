"""
Mode B smoke run — is this model usable with the harness?

Runs a real case from `core/lab/cases/` against a real model, CLEAN and ATTACK,
and prints the traces, the diagnostics and the verdict. Its real job is the
gate §21.9 describes: if a model cannot reliably emit the JSON action
protocol, every metric it produces is biased toward NOT_REACHED, and the model
should be reported as unsuitable rather than scored.

    python -m core.lab.smoke                                   # RGM-001, local ollama
    python -m core.lab.smoke --case RGM-007 --reps 3
    python -m core.lab.smoke --provider groq --model openai/gpt-oss-120b
    python -m core.lab.smoke --scripted                        # no model: replay clean_script
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any, Dict, List, Tuple

from .cases import case_ids, fixture_factory, load_case
from .evaluator import evaluate
from .model_client import ModelClient, ModelConfig
from .runner import RunConfig, ScriptedClient, run_repetitions
from .topology import linear_abc


def _print_trace(title: str, result) -> None:
    print(f"\n--- {title} ({len(result.collector.events)} events) " + "-" * 24)
    for event in result.collector.events:
        bits = [f"{event.step:>3}", f"{event.event_type.value:<20}", f"{event.agent_id or '-':<3}"]
        if event.tool:
            bits.append(event.tool)
        if event.derived_from:
            bits.append(f"<-{list(event.derived_from)}")
        print("  " + " ".join(bits))
    print(f"  diagnostics: {result.diagnostics()}")


def _print_verdict(case: Dict[str, Any], clean, attack) -> None:
    verdict = evaluate(case, attack.collector, clean.collector)
    for agent, impact in verdict.agent_impact.items():
        print(f"  {agent}: {impact.level.value:<16} evidence={list(impact.evidence)}")
    print(f"  objective:      {verdict.objective.level.value} evidence={list(verdict.objective.evidence)}")
    print(f"  containment:    {verdict.containment.status}"
          f" {verdict.containment.agent or ''} ({verdict.containment.mechanism or '-'})")
    print(f"  system outcome: {verdict.system_outcome.value}")


def _suitability(pairs: List[Tuple[Any, Any]]) -> int:
    """§21.9's gate. Parse failures are not a score — a model that cannot
    emit the action protocol biases every metric toward NOT_REACHED, so it is
    reported as unsuitable instead of being ranked.
    """
    steps = sum(r.step_count for pair in pairs for r in pair)
    failures = sum(r.parse_failure_count for pair in pairs for r in pair)
    calls = sum(r.model_call_count for pair in pairs for r in pair)
    rate = failures / steps if steps else 0.0

    reasons: Dict[str, int] = {}
    for pair in pairs:
        for result in pair:
            for event in result.collector.events:
                if event.event_type.value == "agent_finished":
                    key = (event.metadata or {}).get("reason", "unknown")
                    reasons[key] = reasons.get(key, 0) + 1

    print("\n--- HARNESS SUITABILITY " + "-" * 28)
    print(f"  runs:           {len(pairs) * 2} ({len(pairs)} pairs)")
    print(f"  model calls:    {calls}")
    print(f"  parse failures: {failures} / {steps} steps = {rate:.1%}")
    print(f"  agent endings:  {reasons}")
    if rate > 0.10:
        print("  VERDICT: UNSUITABLE — above the ~10% gate in §21.9; scores would be biased")
        return 2
    if reasons.get("max_steps"):
        # Not a parse problem: the model emits valid actions but never stops.
        # Those agents burn the whole step budget, which lengthens trajectories
        # and adds drift that has nothing to do with the attack (§10.8).
        print("  VERDICT: usable, but some agents never called finish — check max_steps bias")
        return 0
    print("  VERDICT: usable with this harness")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="RGM-001", choices=case_ids(), help="case to run")
    parser.add_argument("--reps", type=int, default=1, help="CLEAN/ATTACK pairs to run")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "nvidia", "groq"])
    parser.add_argument("--model", default=None, help="model id (default: $LAB_MODEL or llama3.1:latest)")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--scripted", action="store_true",
                        help="replay the case's clean_script instead of calling a model (no network)")
    parser.add_argument("--quiet", action="store_true", help="verdict and diagnostics only")
    args = parser.parse_args()

    case = load_case(args.case)
    model_config = ModelConfig.from_env(provider=args.provider, model=args.model)

    if args.scripted:
        client: Any = ScriptedClient(case["clean_script"])
        print(f"model:  (scripted — replaying {args.case} clean_script)")
    else:
        client = ModelClient(model_config)
        print(f"model:  {model_config.provider} / {model_config.model}")
        print(f"endpoint: {client.endpoint}")

    print(f"case:   {case['id']} — {case['title']}")
    print(f"attack: {case['attack']['family']} entering at {case['attack']['injection_point']}"
          f" via {case['attack']['delivery']['channel']}")

    config = RunConfig(topology=linear_abc(), model=model_config, max_steps=args.max_steps)
    pairs = await run_repetitions(
        case, fixture_factory(case), config, client, reps=args.reps, experiment_id="smoke",
    )

    for n, (clean, attack) in enumerate(pairs, start=1):
        for result in (clean, attack):
            if result.harness_error:
                print(f"\nHARNESS ERROR in {result.mode} rep {n}: {result.harness_error}")
                return 1
        if not args.quiet:
            _print_trace(f"rep {n} CLEAN", clean)
            _print_trace(f"rep {n} ATTACK", attack)
        print(f"\n--- rep {n} VERDICT " + "-" * 36)
        _print_verdict(case, clean, attack)

    return _suitability(pairs)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
