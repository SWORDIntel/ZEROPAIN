"""Run synthetic cross-state belief/claim integrity scenarios."""

from __future__ import annotations

import argparse
from dataclasses import asdict

from research.dissociation.belief_network import (
    BeliefNetworkConfig,
    BeliefNetworkParameters,
    FactEvent,
    simulate_belief_network,
)
from research.dissociation.model import MechanismInput
from research.dissociation.state_network import EventKind, TimelineEvent
from research.dissociation.verified_io import write_json


SCENARIOS = {
    "baseline": MechanismInput(),
    "meth": MechanismInput(meth=0.75),
    "nmda": MechanismInput(nmda_antagonism=0.60),
    "meth_nmda": MechanismInput(meth=0.75, nmda_antagonism=0.60),
    "wake_disruption": MechanismInput(wake_anchor_disruption=0.90),
    "meth_wake_disruption": MechanismInput(
        meth=0.75,
        wake_anchor_disruption=0.90,
    ),
    "meth_nmda_wake_disruption": MechanismInput(
        meth=0.75,
        nmda_antagonism=0.60,
        wake_anchor_disruption=0.90,
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


def make_facts(steps: int) -> list[FactEvent]:
    truth_pattern = (1, 1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1)
    facts = []
    for idx, truth in enumerate(truth_pattern):
        fraction = (idx + 1) / (len(truth_pattern) + 1)
        facts.append(
            FactEvent(
                step=min(steps - 1, int(fraction * steps)),
                truth=truth,
                salience=0.55 + 0.40 * ((idx % 3) / 2),
                label=f"fact_{idx + 1:02d}",
            )
        )
    return facts


def make_timeline(config: BeliefNetworkConfig) -> list[TimelineEvent]:
    return [
        TimelineEvent(step=step, kind=EventKind.WAKE, label="wake_sync")
        for step in range(config.sync_interval - 1, config.steps, config.sync_interval)
    ]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--states", type=int, default=4)
    p.add_argument("--steps", type=int, default=480)
    p.add_argument("--seed", type=int, default=37)
    p.add_argument("--sync-interval", type=int, default=96)
    p.add_argument("--max-coconscious", type=int, default=2)
    p.add_argument("--trace", action="store_true")
    p.add_argument("--output", default="runs/dissociation_belief_network.json")
    return p


def build_payload(args: argparse.Namespace) -> dict:
    config = BeliefNetworkConfig(
        n_states=args.states,
        steps=args.steps,
        seed=args.seed,
        sync_interval=args.sync_interval,
        max_coconscious=args.max_coconscious,
    )
    params = BeliefNetworkParameters()
    facts = make_facts(config.steps)
    timeline = make_timeline(config)

    results = {}
    traces = {}
    for name, inputs in SCENARIOS.items():
        result = simulate_belief_network(
            inputs,
            facts,
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
                "mean_trust": trace.mean_trust,
                "consistency": trace.consistency,
                "truth_accuracy": trace.truth_accuracy,
                "regime": trace.regime,
                "withholding_events": trace.withholding_events,
                "false_report_events": trace.false_report_events,
            }
        else:
            results[name] = result.to_dict()

    payload = {
        "schema_version": 1,
        "model": "synthetic_cross_state_belief_integrity",
        "warning": (
            "Research toy model only. 'False reporting' is a synthetic network variable, "
            "not a general claim about DID or any patient population."
        ),
        "config": asdict(config),
        "parameters": asdict(params),
        "facts": [asdict(fact) for fact in facts],
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
    return payload


def _relations(payload: dict):
    failures = []
    for name, result in payload["results"].items():
        expected = result["sync_expected"]
        completed = result["sync_completed"]
        if completed > expected:
            failures.append(f"{name}: sync_completed={completed} > sync_expected={expected}")
        if result["false_report_events"] > result["communication_opportunities"]:
            failures.append(f"{name}: false reports exceed communication opportunities")
        if result["withholding_events"] > result["communication_opportunities"]:
            failures.append(f"{name}: withholding exceeds communication opportunities")
    return (not failures, "; ".join(failures[:6]))


def main() -> int:
    args = _parser().parse_args()
    payload = build_payload(args)
    out = write_json(
        args.output,
        payload,
        label="dissociation.belief_network",
        relations=[_relations],
        replay=lambda: build_payload(args),
        metadata={
            "seed": args.seed,
            "steps": args.steps,
            "states": args.states,
            "trace": args.trace,
        },
    )

    print(f"Wrote {len(payload['results'])} belief-network scenarios to {out}")
    for name, result in payload["results"].items():
        print(
            f"{name:28s} "
            f"trust={result['mean_pairwise_trust']:.3f} "
            f"cons={result['belief_consistency']:.3f} "
            f"truth={result['truth_accuracy']:.3f} "
            f"withhold={result['withholding_rate']:.3f} "
            f"false={result['false_report_rate']:.3f} "
            f"regime={result['final_regime']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
