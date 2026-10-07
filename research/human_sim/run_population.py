"""Run HumanSim across a correlated virtual physiology population.

The CSV is expected to come from httk::httkpop_generate() or a compatible table.
The imported physiology is source-backed at the population-generator level, but this
reduced HumanSim adapter still performs explicit lumping/conversion approximations.

The compound disposition and target panel used by this milestone remain synthetic
software fixtures. No human dose conversion is provided.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

from research.human_sim.disposition import synthetic_reference_disposition
from research.human_sim.engine import simulate_human_chain, synthetic_target_panel
from research.human_sim.population import (
    detect_population_format,
    load_population_csv,
    summarize_population,
)
from research.human_sim.provenance import sources_dict
from zeropain.verified_io import write_json


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("population_csv")
    p.add_argument("--format", choices=("auto", "httk", "pksim"), default="auto")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--duration-h", type=float, default=6.0)
    p.add_argument("--dt-h", type=float, default=0.05)
    p.add_argument("--initial-central-units", type=float, default=1.0)
    p.add_argument("--output", default="runs/human_sim_population.json")
    return p


def _q(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(array)),
        "sd": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
        "q05": float(np.quantile(array, 0.05)),
        "q50": float(np.quantile(array, 0.50)),
        "q95": float(np.quantile(array, 0.95)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def build_payload(args: argparse.Namespace) -> dict:
    path = Path(args.population_csv)
    selected_format = detect_population_format(path) if args.format == "auto" else args.format
    individuals = load_population_csv(path, format=selected_format)
    if args.limit > 0:
        individuals = individuals[: args.limit]
    if not individuals:
        raise ValueError("no virtual individuals selected")

    disposition = synthetic_reference_disposition()
    targets = synthetic_target_panel()

    brain_peak = []
    mass_error = []
    target_peak_occupancy = {name: [] for name in targets}
    target_mean_signal = {name: [] for name in targets}

    for individual in individuals:
        result = simulate_human_chain(
            individual.physiology,
            disposition,
            targets,
            duration_h=args.duration_h,
            dt_h=args.dt_h,
            initial_central_amount=args.initial_central_units,
        )
        summary = result.summary()
        brain_peak.append(summary["pbpk"]["peak_brain_free_concentration"])
        mass_error.append(summary["pbpk"]["max_abs_mass_balance_error"])
        for name, target in summary["targets"].items():
            target_peak_occupancy[name].append(target["peak_occupancy"])
            target_mean_signal[name].append(target["mean_signal_magnitude"])

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    population_summary = summarize_population(individuals)
    source_id = "httk_population" if selected_format == "httk" else "pksim_population"
    evidence_ids = [source_id]
    if selected_format == "httk":
        evidence_ids.append("httk_tissue")

    return {
        "schema_version": 1,
        "model": "human_sim_correlated_virtual_population",
        "warning": (
            "Physiology rows are imported from an external virtual-population CSV, "
            "but the reduced compartment mapping and current compound/target values "
            "remain research approximations. No clinical dosing inference."
        ),
        "population_source": {
            "input_path": str(path),
            "sha256": digest,
            "format": selected_format,
            "source_id": source_id,
            "evidence": sources_dict(evidence_ids),
            "selected_individuals": len(individuals),
        },
        "population_physiology_summary": population_summary.to_dict(),
        "model_input": {
            "duration_h": args.duration_h,
            "dt_h": args.dt_h,
            "initial_central_units": args.initial_central_units,
            "disposition": disposition.to_dict(),
        },
        "outcomes": {
            "peak_brain_free_concentration": _q(brain_peak),
            "mass_balance_error": _q(mass_error),
            "targets": {
                name: {
                    "peak_occupancy": _q(target_peak_occupancy[name]),
                    "mean_signal_magnitude": _q(target_mean_signal[name]),
                }
                for name in targets
            },
        },
    }


def _relations(payload: dict):
    failures = []
    if payload["population_source"]["selected_individuals"] < 1:
        failures.append("population empty")
    if payload["outcomes"]["mass_balance_error"]["max"] > 1e-8:
        failures.append("population mass-balance residual exceeded 1e-8")
    for name, target in payload["outcomes"]["targets"].items():
        for metric in ("peak_occupancy", "mean_signal_magnitude"):
            stats = target[metric]
            if stats["min"] < 0.0 or stats["max"] > 1.0:
                failures.append(f"{name}.{metric} outside [0,1]")
    return (not failures, "; ".join(failures[:8]))


def main() -> int:
    args = _parser().parse_args()
    if args.limit < 0:
        raise ValueError("--limit cannot be negative")
    if args.initial_central_units < 0:
        raise ValueError("--initial-central-units cannot be negative")

    payload = build_payload(args)
    out = write_json(
        args.output,
        payload,
        label="human_sim.population",
        relations=[_relations],
        metadata={
            "population_sha256": payload["population_source"]["sha256"],
            "selected_individuals": payload["population_source"]["selected_individuals"],
        },
    )
    print(f"Wrote HumanSim population result to {out}")
    print(
        f"n={payload['population_source']['selected_individuals']} "
        f"brain_q05={payload['outcomes']['peak_brain_free_concentration']['q05']:.6f} "
        f"brain_q50={payload['outcomes']['peak_brain_free_concentration']['q50']:.6f} "
        f"brain_q95={payload['outcomes']['peak_brain_free_concentration']['q95']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
