"""Scenario runner for the state-specific memory/trust network."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from research.dissociation.model import MechanismInput
from research.dissociation.state_network import (
    EventKind,
    StateNetworkConfig,
    StateNetworkParameters,
    TimelineEvent,
    build_default_timeline,
    simulate_state_network,
)


SCENARIOS = {
    "baseline": MechanismInput(),
    "meth": MechanismInput(meth=0.75),
    "nmda": MechanismInput(nmda_antagonism=0.60),
    "meth_nmda": MechanismInput(meth=0.75, nmda_antagonism=0.60),
    "wake_disruption": MechanismInput(wake_anchor_disruption=0.85),
    "meth_wake_disruption": MechanismInput(
        meth=0.75,
        wake_anchor_disruption=0.85,
    ),
    "meth_nmda_wake_disruption": MechanismInput(
        meth=0.75,
        nmda_antagonism=0.60,
        wake_anchor_disruption=0.85,
    ),
    "meth_mor_partial": MechanismInput(
        meth=0.75,
        mor_partial_agonism=0.60,
    ),
    "meth_kor_agonism": MechanismInput(
        meth=0.75,
        kor_agonism=0.60,
    ),
    "meth_kor_antagonism": MechanismInput(
        meth=0.75,
        kor_antagonism=0.60,
    ),
}


def build_timeline(config: StateNetworkConfig) -> list[TimelineEvent]:
    timeline = build_default_timeline(config)
    # Add several non-pharmacological stressors to all scenarios so drug/system
    # perturbations are tested against the same event stream.
    for fraction, intensity, label in (
        (0.18, 0.55, "stress_A"),
        (0.43, 0.75, "stress_B"),
        (0.67, 0.45, "stress_C"),
        (0.82, 0.80, "stress_D"),
    ):
        timeline.append(
            TimelineEvent(
                step=min(config.steps - 1, int(config.steps * fraction)),
                kind=EventKind.STRESS,
                intensity=intensity,
                label=label,
            )
        )
    return sorted(timeline, key=lambda event: event.step)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--states", type=int, default=4)
    p.add_argument("--steps", type=int, default=480)
    p.add_argument("--seed", type=int, default=23)
    p.add_argument("--max-coconscious", type=int, default=2)
    p.add_argument("--sync-interval", type=int, default=96)
    p.add_argument("--output", default="runs/dissociation_state_network.json")
    p.add_argument("--trace", action="store_true")
    return p


def main() -> int:
    args = _parser().parse_args()
    config = StateNetworkConfig(
        n_states=args.states,
        steps=args.steps,
        seed=args.seed,
        max_coconscious=args.max_coconscious,
        sync_interval=args.sync_interval,
    )
    params = StateNetworkParameters()
    timeline = build_timeline(config)

    results = {}
    traces = {}
    for name, inputs in SCENARIOS.items():
        result = simulate_state_network(
            inputs,
            config=config,
            params=params,
            timeline=timeline,
            return_trace=args.trace,
        )
        if args.trace:
            summary, trace = result
            results[name] = summary.to_dict()
            traces[name] = {
                "executive": trace.executive,
                "coconscious": [list(states) for states in trace.coconscious],
                "mean_trust": trace.mean_trust,
                "memory_consistency": trace.memory_consistency,
                "withholding_events": trace.withholding_events,
            }
        else:
            results[name] = result.to_dict()

    payload = {
        "schema_version": 1,
        "model": "synthetic_state_specific_memory_trust_network",
        "warning": (
            "Research toy model only. Inputs are dimensionless perturbations, "
            "not drug doses or treatment recommendations."
        ),
        "config": asdict(config),
        "parameters": asdict(params),
        "timeline": [
            {
                "step": event.step,
                "kind": event.kind.value,
                "intensity": event.intensity,
                "label": event.label,
            }
            for event in timeline
        ],
        "scenarios": {name: asdict(inputs) for name, inputs in SCENARIOS.items()},
        "results": results,
    }
    if args.trace:
        payload["traces"] = traces

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(results)} state-network scenarios to {out}")
    for name, result in results.items():
        print(
            f"{name:28s} "
            f"switch={result['switch_rate']:.3f} "
            f"co={result['mean_coconscious_states']:.2f} "
            f"trust={result['mean_pairwise_trust']:.3f} "
            f"mem={result['memory_consistency']:.3f} "
            f"withhold={result['withholding_rate']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
