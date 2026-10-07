"""Run discrete identity-state graph scenarios."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from research.dissociation.model import MechanismInput
from research.dissociation.state_graph import (
    StateGraphConfig,
    StateGraphParameters,
    simulate_state_graph,
)


SCENARIOS = {
    "baseline": MechanismInput(),
    "meth": MechanismInput(meth=0.75),
    "wake_anchor_disruption": MechanismInput(wake_anchor_disruption=0.85),
    "meth_plus_wake_disruption": MechanismInput(
        meth=0.75,
        wake_anchor_disruption=0.85,
    ),
    "nmda": MechanismInput(nmda_antagonism=0.60),
    "meth_plus_nmda": MechanismInput(
        meth=0.75,
        nmda_antagonism=0.60,
    ),
    "meth_plus_mor_partial": MechanismInput(
        meth=0.75,
        mor_partial_agonism=0.60,
    ),
    "meth_plus_kor_agonism": MechanismInput(
        meth=0.75,
        kor_agonism=0.60,
    ),
    "meth_plus_kor_antagonism": MechanismInput(
        meth=0.75,
        kor_antagonism=0.60,
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", type=int, default=4)
    parser.add_argument("--steps", type=int, default=480)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--sync-interval", type=int, default=96)
    parser.add_argument("--output", default="runs/dissociation_state_graph.json")
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = StateGraphConfig(
        n_states=args.states,
        steps=args.steps,
        seed=args.seed,
        sync_interval=args.sync_interval,
    )
    params = StateGraphParameters()

    results = {
        name: simulate_state_graph(inputs, config=config, params=params)
        for name, inputs in SCENARIOS.items()
    }

    payload = {
        "schema_version": 1,
        "model": "synthetic_identity_state_graph",
        "warning": (
            "Research toy model only. Inputs are dimensionless and are not doses "
            "or treatment recommendations."
        ),
        "config": asdict(config),
        "parameters": asdict(params),
        "scenarios": {name: asdict(inputs) for name, inputs in SCENARIOS.items()},
        "results": {name: result.to_dict() for name, result in results.items()},
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(results)} state-graph scenarios to {output}")
    for name, result in results.items():
        print(
            f"{name:30s} switches={result.switches:4d} "
            f"entropy={result.normalized_occupancy_entropy:0.3f} "
            f"memory_div={result.memory_divergence:0.3f} "
            f"sync={result.synchronization_completion_rate:0.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
