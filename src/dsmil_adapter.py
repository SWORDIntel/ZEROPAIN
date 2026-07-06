#!/usr/bin/env python3
"""
ZeroPain DSMIL Adapter
Wraps and exposes the CLI/TUI entrypoints and handles a structured JSON contract
matching PatientGenerationConfig, ProtocolConfig, and CompoundProfile.
"""

import sys
import json
import traceback
from typing import List, Dict, Optional, Any
from opioid_analysis_tools import CompoundDatabase, CompoundProfile
from opioid_optimization_framework import ProtocolConfig
from patient_simulation import PatientGenerationConfig, PopulationSimulation


def _to_scalar(v: Any) -> Any:
    """Coerce numpy scalars to plain Python types for JSON safety."""
    try:
        import numpy as np
        if isinstance(v, np.generic):
            return v.item()
    except ImportError:
        pass
    return v


def run_cli(args: List[str]) -> int:
    """
    CLI entrypoint for DSMIL adapter.
    Runs pipeline operations or simulation based on CLI arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(description="ZeroPain DSMIL Adapter CLI")
    parser.add_argument('--simulate', action='store_true', help='Run simulation')
    parser.add_argument('--optimize', action='store_true', help='Run protocol optimisation')
    parser.add_argument('--list-compounds', action='store_true', help='List available compounds')
    parser.add_argument('--payload', type=str, help='Path to JSON payload file')
    parser.add_argument('--compounds', nargs='+', default=['SR-17018'], help='Compounds')
    parser.add_argument('--doses', nargs='+', type=float, default=[10.0], help='Doses (mg)')
    parser.add_argument('--frequencies', nargs='+', type=int, default=[2], help='Frequencies')
    parser.add_argument('--n-patients-sim', type=int, default=1000, help='Population size (scalable)')
    parser.add_argument('--duration-days', type=int, default=90, help='Simulation duration')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--run-id', default=None, help='Run ID for checkpointing')
    parser.add_argument('--batch-size', type=int, default=256, help='Checkpoint batch size')
    parser.add_argument('--backend', choices=['local', 'ray', 'dask'], default='local')
    parser.add_argument('--tolerance-model', choices=['linear', 'sigmoid', 'lagged'], default='sigmoid')
    parser.add_argument('--addiction-slope', type=float, default=0.005)
    parser.add_argument('--output', default=None, help='Write JSON results here')

    parsed = parser.parse_args(args)
    db = CompoundDatabase()

    if parsed.payload:
        with open(parsed.payload, 'r') as f:
            payload = json.load(f)
        results = process_request(payload)
        print(json.dumps(results, indent=2, default=str))
        return 0

    if parsed.list_compounds:
        results = process_request({'operation': 'list_compounds'})
        print(json.dumps(results, indent=2, default=str))
        return 0

    protocol = ProtocolConfig(
        compounds=parsed.compounds,
        doses=parsed.doses,
        frequencies=parsed.frequencies,
    )
    tolerance_config = {
        'tolerance': {
            'model': parsed.tolerance_model,
            'addiction_slope': parsed.addiction_slope,
        }
    }

    if parsed.simulate or parsed.optimize:
        from pipeline.distributed_runner import DistributedRunner
        runner = DistributedRunner(
            backend=parsed.backend,
            run_id=parsed.run_id,
        )
        output: Dict[str, Any] = {}

        if parsed.optimize:
            from opioid_optimization_framework import run_local_optimization
            opt = run_local_optimization(
                protocol=protocol, compound_db=db,
                n_patients=min(parsed.n_patients_sim, 500),
                duration_days=parsed.duration_days, seed=parsed.seed,
            )
            output['optimization'] = {
                'optimal_doses': dict(zip(opt.optimal_protocol.compounds, opt.optimal_protocol.doses)),
                'safety_score': opt.safety_score,
                'success_rate': opt.success_rate,
            }

        if parsed.simulate:
            sim = PopulationSimulation(db)
            gen_config = PatientGenerationConfig(population_size=parsed.n_patients_sim)
            sim_results = sim.run_simulation(
                n_patients=parsed.n_patients_sim,
                protocol=protocol,
                duration_days=parsed.duration_days,
                seed=parsed.seed,
                generation_config=gen_config,
                runner=runner,
                checkpoint_stage='simulation',
                batch_size=parsed.batch_size,
                tolerance_config=tolerance_config,
            )
            output['simulation'] = {
                k: v for k, v in sim_results.items()
                if isinstance(v, (int, float, str, bool, type(None)))
            }

        out_json = json.dumps(output, indent=2, default=str)
        if parsed.output:
            from pathlib import Path
            Path(parsed.output).write_text(out_json, encoding='utf-8')
            print(f'Results written to {parsed.output}')
        else:
            print(out_json)
        return 0

    parser.print_help()
    return 0

def run_tui() -> None:
    """
    TUI entrypoint for DSMIL adapter.
    """
    from zeropain_tui import ZeroPainTUI
    tui = ZeroPainTUI()
    tui.run()

def process_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    JSON-in / JSON-out gateway for hub-driven DSMIL integration.

    Supported operations (``payload['operation']``):
      - ``'list_compounds'`` – return compound catalogue.
      - ``'optimize'``       – run protocol optimisation, return optimal doses.
      - ``'simulate'``       – run patient simulation (default).

    Population sizing is fully dynamic via ``patient_count``.
    """
    try:
        db = CompoundDatabase()
        operation = payload.get('operation', 'simulate')

        if operation == 'list_compounds':
            compounds = []
            for name in sorted(db.list_compounds()):
                c = db.get_compound(name)
                compounds.append({
                    'name': c.name,
                    'ki_mor': c.ki_mor if c.ki_mor != float('inf') else None,
                    'ki_dor': c.ki_dor if c.ki_dor != float('inf') else None,
                    'ki_kor': c.ki_kor if c.ki_kor != float('inf') else None,
                    'metabolic_pathways': getattr(c, 'metabolic_pathways', {}),
                    'g_protein_bias': c.g_protein_bias,
                    'safety_score': c.calculate_safety_score(),
                })
            return {'ok': True, 'result': {'compounds': compounds}}

        # Register any custom compounds supplied in the payload.
        # Support both 'custom_compounds' key and the legacy pattern where
        # 'compounds' is a list of dicts (compound profiles) rather than names.
        raw_compounds = payload.get('compounds', [])
        if raw_compounds and isinstance(raw_compounds[0], dict):
            # Legacy: list of compound dicts → register as custom, names from protocol
            for comp_data in raw_compounds:
                try:
                    comp = CompoundProfile.from_dict(comp_data)
                    db.add_custom_compound(comp)
                except Exception:
                    pass
        for comp_data in payload.get('custom_compounds', []):
            try:
                comp = CompoundProfile.from_dict(comp_data)
                db.add_custom_compound(comp)
            except Exception:
                pass

        # Build protocol
        proto_data = payload.get('protocol_config', payload.get('protocol', {}))
        # If raw_compounds was names (strings), use them; otherwise fall back to protocol
        if raw_compounds and isinstance(raw_compounds[0], str):
            default_names = raw_compounds
        else:
            default_names = ['SR-17018']
        compound_names = proto_data.get('compounds', payload.get('compound_names', default_names))
        doses = proto_data.get('doses', payload.get('doses', [10.0] * len(compound_names)))
        frequencies = proto_data.get('frequencies', payload.get('frequencies', [2] * len(compound_names)))
        protocol = ProtocolConfig(compounds=compound_names, doses=doses, frequencies=frequencies)

        # Build generation config
        gen_data = payload.get('patient_generation_config', {})
        # Accept both patient_count (new) and n_patients_sim (legacy)
        n_patients = payload.get('patient_count', payload.get('n_patients_sim', gen_data.get('population_size', 1000)))
        gen_cfg = PatientGenerationConfig(
            population_size=n_patients,
            sex_ratio_male=1.0 - payload.get('sex_ratio_female', 0.5),
        )

        duration_days = payload.get('duration_days', proto_data.get('duration', 90))
        seed = payload.get('seed', 42)
        batch_size = payload.get('batch_size', 256)
        run_id = payload.get('run_id')

        # Tolerance/addiction config — accept both flat and nested forms
        tc = payload.get('tolerance_config', {})
        if isinstance(tc, dict) and 'tolerance' in tc:
            # Already nested: {"tolerance": {...}}
            tolerance_config = tc
        elif isinstance(tc, dict) and 'model' in tc:
            # Flat with model key: wrap it
            tolerance_config = {'tolerance': tc}
        else:
            tolerance_config = tc

        from pipeline.distributed_runner import DistributedRunner
        runner = DistributedRunner(backend=payload.get('backend', 'local'), run_id=run_id)

        if operation == 'optimize':
            from opioid_optimization_framework import run_local_optimization
            opt = run_local_optimization(
                protocol=protocol, compound_db=db,
                n_patients=min(n_patients, 500),
                duration_days=duration_days, seed=seed,
            )
            return {'ok': True, 'result': {
                'operation': 'optimize',
                'optimal_doses': dict(zip(opt.optimal_protocol.compounds, opt.optimal_protocol.doses)),
                'safety_score': opt.safety_score,
                'success_rate': opt.success_rate,
                'tolerance_rate': opt.tolerance_rate,
                'addiction_rate': opt.addiction_rate,
            }}

        # Default: simulate
        sim = PopulationSimulation(db)
        sim_results = sim.run_simulation(
            n_patients=n_patients,
            protocol=protocol,
            duration_days=duration_days,
            seed=seed,
            generation_config=gen_cfg,
            runner=runner,
            checkpoint_stage='simulation',
            batch_size=batch_size,
            tolerance_config=tolerance_config,
        )
        safe = {k: _to_scalar(v) for k, v in sim_results.items() if isinstance(_to_scalar(v), (int, float, str, bool, type(None)))}
        # Return both wrapped (new) and flat (legacy) keys for backward compatibility
        return {'ok': True, 'result': {'operation': 'simulate', **safe}, **safe}

    except Exception as exc:  # pylint: disable=broad-except
        return {'ok': False, 'error': str(exc), 'traceback': traceback.format_exc()}


# ---------------------------------------------------------------------------
# Standalone entrypoint
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    sys.exit(run_cli())
