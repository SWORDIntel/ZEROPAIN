"""Generate synthetic physiological observations from state-network traces."""

from __future__ import annotations

import argparse
from dataclasses import asdict

from research.dissociation.model import MechanismInput
from research.dissociation.observation_model import (
    FEATURE_NAMES,
    ObservationConfig,
    simulate_observations,
)
from research.dissociation.state_network import (
    StateNetworkConfig,
    StateNetworkParameters,
    simulate_state_network,
)
from research.dissociation.verified_io import write_json


SCENARIOS = {
    "baseline": MechanismInput(),
    "meth": MechanismInput(meth=0.75),
    "nmda": MechanismInput(nmda_antagonism=0.60),
    "meth_nmda": MechanismInput(meth=0.75, nmda_antagonism=0.60),
    "meth_kor_antagonism": MechanismInput(meth=0.75, kor_antagonism=0.60),
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--states", type=int, default=4)
    p.add_argument("--steps", type=int, default=480)
    p.add_argument("--seed", type=int, default=53)
    p.add_argument("--output", default="runs/dissociation_observation_model.json")
    p.add_argument("--include-features", action="store_true")
    return p


def build_payload(args: argparse.Namespace) -> dict:
    state_config = StateNetworkConfig(
        n_states=args.states,
        steps=args.steps,
        seed=args.seed,
        max_coconscious=min(3, args.states),
        sync_interval=96,
    )
    state_params = StateNetworkParameters()
    obs_config = ObservationConfig(
        n_states=args.states,
        seed=args.seed + 100,
    )

    results = {}
    for name, inputs in SCENARIOS.items():
        _, trace = simulate_state_network(
            inputs,
            config=state_config,
            params=state_params,
            return_trace=True,
        )
        observation = simulate_observations(trace, inputs, config=obs_config)
        record = {
            "summary": observation.summary.to_dict(),
            "state_signatures": observation.state_signatures.tolist(),
        }
        if args.include_features:
            record["features"] = observation.features.tolist()
            record["expected_mixture"] = observation.expected_mixture.tolist()
            record["transient_component"] = observation.transient_component.tolist()
        results[name] = record

    return {
        "schema_version": 1,
        "model": "synthetic_state_physiology_observation",
        "warning": (
            "Feature values are standardized synthetic units, not clinical EEG/HR measurements."
        ),
        "feature_names": list(FEATURE_NAMES),
        "state_config": asdict(state_config),
        "observation_config": asdict(obs_config),
        "scenarios": {name: asdict(inputs) for name, inputs in SCENARIOS.items()},
        "results": results,
    }


def main() -> int:
    args = _parser().parse_args()
    payload = build_payload(args)
    out = write_json(
        args.output,
        payload,
        label="dissociation.observation_model",
        replay=lambda: build_payload(args),
        metadata={"seed": args.seed, "steps": args.steps, "states": args.states},
    )

    print(f"Wrote {len(payload['results'])} observation scenarios to {out}")
    for name, record in payload["results"].items():
        summary = record["summary"]
        print(
            f"{name:24s} "
            f"pure_acc={summary['nearest_signature_accuracy_pure']:.3f} "
            f"blends={summary['blended_steps']:4d} "
            f"switch_resid={summary['switch_transient_mean_norm']:.3f} "
            f"nonswitch_resid={summary['nonswitch_mean_residual_norm']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
