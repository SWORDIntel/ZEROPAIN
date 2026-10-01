#!/usr/bin/env python3
"""
ZeroPain DSMIL Adapter
Wraps and exposes the CLI/TUI entrypoints and handles a structured JSON contract
matching PatientGenerationConfig, ProtocolConfig, and CompoundProfile.
"""

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
_CALIBRATED_PARAMS_PATH = ROOT / "calibrated_params.json"

# ---------------------------------------------------------------------------
# Calibrated params helpers
# ---------------------------------------------------------------------------

def _load_calibrated_tolerance_config(
    compound_class: str = "full_agonist",
    path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Load tolerance_config from the fitted calibration file if it exists.
    Returns None if the file is absent or malformed.
    """
    target = path or _CALIBRATED_PARAMS_PATH
    if not target.exists():
        return None
    try:
        with target.open("r", encoding="utf-8") as f:
            params = json.load(f)
        tol_key = "tolerance" if compound_class == "full_agonist" else "tolerance_partial_agonist"
        tol = params.get(tol_key, params.get("tolerance", {}))
        add = params.get("addiction", {})
        tol_compat = dict(tol)
        if "addiction_slope" not in tol_compat and "addiction_slope" in add:
            tol_compat["addiction_slope"] = add["addiction_slope"]
        if "addiction_threshold" not in tol_compat and "addiction_threshold" in add:
            tol_compat["addiction_threshold"] = add["addiction_threshold"]
        return {
            "tolerance": tol_compat,
            "addiction": add
        }
    except Exception:
        return None

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
    parser.add_argument('--compounds', nargs='+', default=['SR-16435'], help='Compounds')
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
    parser.add_argument('--liver-disease-rate', type=float, default=None, help='Override liver disease prevalence (0.0 - 1.0)')
    parser.add_argument('--kidney-disease-rate', type=float, default=None, help='Override kidney disease prevalence (0.0 - 1.0)')
    parser.add_argument('--elderly-skew', action='store_true', help='Shift age distribution to elderly (>75)')
    parser.add_argument('--high-tolerance-skew', action='store_true', help='Artificially increase baseline tolerance globally')
    parser.add_argument('--polypharmacy-rate', type=float, default=None, help='Multiplier for pre-existing medication prevalence')
    parser.add_argument('--output', default=None, help='Write JSON results here')

    # Tensor engine & GPU acceleration options
    parser.add_argument('--tensor-engine', action='store_true', help='Use PyTorch/CUDA tensor vectorized simulation engine')
    parser.add_argument('--gpu', action='store_true', help='Enable GPU acceleration (CUDA) for tensor engine')
    parser.add_argument('--device', choices=['cpu', 'cuda', 'auto'], default=None, help='Device for tensor simulation')
    parser.add_argument('--chunk-size', type=int, default=250000, help='Chunk size for vectorized batching in tensor engine')
    parser.add_argument('--cohort', choices=['standard', 'polysubstance_crisis', 'multi_organ_failure', 'zombie_market'], default='standard', help='Preconfigured cohort preset')

    # Pharmacogenomics (PGx) parameters
    parser.add_argument('--pgx-ugt2b7-poor-rate', type=float, default=None, help='Prevalence of UGT2B7 poor metabolizers')
    parser.add_argument('--pgx-cyp2d6-poor-rate', type=float, default=None, help='Prevalence of CYP2D6 poor metabolizers')
    parser.add_argument('--pgx-cyp3a4-poor-rate', type=float, default=None, help='Prevalence of CYP3A4 poor metabolizers')
    parser.add_argument('--pgx-oprm1-a118g-rate', type=float, default=None, help='Prevalence of OPRM1 A118G variant')
    parser.add_argument('--pgx-comt-met-rate', type=float, default=None, help='Prevalence of COMT Val158Met variant')
    parser.add_argument('--pgx-abcb1-efflux-loss', type=float, default=None, help='Prevalence of ABCB1 P-gp efflux loss')

    # Street Adulterants & Polysubstance parameters
    parser.add_argument('--street-fentanyl-rate', type=float, default=None, help='Prevalence of street fentanyl exposure')
    parser.add_argument('--xylazine-rate', type=float, default=None, help='Prevalence of Xylazine (tranq) exposure')
    parser.add_argument('--nitazene-rate', type=float, default=None, help='Prevalence of Nitazene exposure')
    parser.add_argument('--alcohol-rate', type=float, default=None, help='Prevalence of concurrent alcohol abuse')

    # Multi-Organ Impairment parameters
    parser.add_argument('--child-pugh-c-rate', type=float, default=None, help='Prevalence of severe hepatic failure (Child-Pugh C)')
    parser.add_argument('--ckd-stage-5-rate', type=float, default=None, help='Prevalence of end-stage renal disease (CKD Stage 5)')
    parser.add_argument('--copd-severe-rate', type=float, default=None, help='Prevalence of severe COPD / sleep apnea with lost hypoxic drive')
    parser.add_argument('--cachexia-rate', type=float, default=None, help='Prevalence of severe cachexia (contracted Vd)')
    parser.add_argument('--morbid-obesity-rate', type=float, default=None, help='Prevalence of morbid obesity (BMI > 50)')

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
    tolerance_config = _load_calibrated_tolerance_config()
    if not tolerance_config:
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
                compounds=parsed.compounds,
                n_patients=min(parsed.n_patients_sim, 500)
            )
            output['optimization'] = {
                'optimal_doses': dict(zip(opt.optimal_protocol.compounds, opt.optimal_protocol.doses)),
                'safety_score': opt.safety_score,
                'success_rate': opt.success_rate,
            }

        if parsed.simulate:
            if parsed.tensor_engine or parsed.gpu:
                try:
                    import tensor_simulation
                except ImportError:
                    from src import tensor_simulation

                device = 'cuda' if parsed.gpu else (parsed.device or 'auto')
                proto = tensor_simulation.TensorProtocolConfig(
                    compounds=parsed.compounds,
                    doses=parsed.doses,
                    frequencies=[float(f) for f in parsed.frequencies],
                    duration_days=parsed.duration_days,
                )

                overrides: Dict[str, Any] = {}
                if parsed.pgx_ugt2b7_poor_rate is not None:
                    overrides['ugt2b7_poor_rate'] = parsed.pgx_ugt2b7_poor_rate
                if parsed.pgx_cyp2d6_poor_rate is not None:
                    overrides['cyp2d6_pm_rate'] = parsed.pgx_cyp2d6_poor_rate
                if parsed.pgx_cyp3a4_poor_rate is not None:
                    overrides['cyp3a4_pm_rate'] = parsed.pgx_cyp3a4_poor_rate
                if parsed.pgx_oprm1_a118g_rate is not None:
                    overrides['oprm1_gg_rate'] = parsed.pgx_oprm1_a118g_rate
                if parsed.pgx_comt_met_rate is not None:
                    overrides['comt_val_val_rate'] = parsed.pgx_comt_met_rate
                if parsed.pgx_abcb1_efflux_loss is not None:
                    overrides['abcb1_deficient_rate'] = parsed.pgx_abcb1_efflux_loss
                if parsed.street_fentanyl_rate is not None:
                    overrides['street_fentanyl_rate'] = parsed.street_fentanyl_rate
                if parsed.xylazine_rate is not None:
                    overrides['xylazine_rate'] = parsed.xylazine_rate
                if parsed.nitazene_rate is not None:
                    overrides['nitazene_rate'] = parsed.nitazene_rate
                if parsed.alcohol_rate is not None:
                    overrides['alcohol_rate'] = parsed.alcohol_rate
                if parsed.child_pugh_c_rate is not None:
                    overrides['child_pugh_c_rate'] = parsed.child_pugh_c_rate
                if parsed.ckd_stage_5_rate is not None:
                    overrides['ckd_stage5_esrd_rate'] = parsed.ckd_stage_5_rate
                if parsed.copd_severe_rate is not None:
                    overrides['copd_gold4_rate'] = parsed.copd_severe_rate
                if parsed.cachexia_rate is not None:
                    overrides['cachexia_rate'] = parsed.cachexia_rate
                if parsed.morbid_obesity_rate is not None:
                    overrides['morbid_obesity_rate'] = parsed.morbid_obesity_rate

                cohort_target: Any = parsed.cohort
                if overrides:
                    base = tensor_simulation.COHORT_PRESETS.get(parsed.cohort, tensor_simulation.CohortConfig())
                    base_dict = base.to_dict() if hasattr(base, 'to_dict') else dict(base)
                    base_dict.update(overrides)
                    cohort_target = tensor_simulation.CohortConfig(**base_dict)

                summary = tensor_simulation.run_tensor_simulation(
                    total_patients=parsed.n_patients_sim,
                    protocol=proto,
                    cohort=cohort_target,
                    chunk_size=parsed.chunk_size,
                    device=device,
                    seed=parsed.seed,
                    verbose=True,
                )
                output['simulation'] = summary.to_dict() if hasattr(summary, 'to_dict') else dict(summary)
            else:
                sim = PopulationSimulation(db)
                gen_kwargs = {'population_size': parsed.n_patients_sim}
                if parsed.elderly_skew:
                    from patient_simulation import AgeDistribution
                    gen_kwargs['age_distribution'] = AgeDistribution(alpha=5.0, beta=2.0, min_age=65, max_age=95)
                
                gen_config = PatientGenerationConfig(**gen_kwargs)
                
                # Apply demographic overrides
                if parsed.liver_disease_rate is not None:
                    gen_config.comorbidity_prevalence['liver_disease'] = parsed.liver_disease_rate
                if parsed.kidney_disease_rate is not None:
                    gen_config.comorbidity_prevalence['kidney_disease'] = parsed.kidney_disease_rate
                if parsed.polypharmacy_rate is not None:
                    for k, v in gen_config.pre_existing_medications.items():
                        v.prevalence = min(1.0, v.prevalence * parsed.polypharmacy_rate)
                if parsed.high_tolerance_skew:
                    from patient_simulation import MedicationProfile
                    gen_config.pre_existing_medications['street_opioids'] = MedicationProfile(
                        name="Street Fentanyl/Heroin",
                        prevalence=1.0, # 100% of the population
                        baseline_tolerance=0.90, # 90% receptor downregulation
                        sensitivity_multiplier=0.4, # Burned out receptors
                        side_effect_bias=0.2
                    )
                
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
            default_names = ['SR-16435']
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

        # Tolerance/addiction config — priority chain:
        #   1. Explicit payload tolerance_config
        #   2. Calibrated params from calibrated_params.json (if use_calibrated not False)
        #   3. Built-in defaults
        tc = payload.get('tolerance_config')
        use_calibrated = payload.get('use_calibrated', True)

        if tc:
            # Explicit override — normalise nested vs flat form
            if isinstance(tc, dict) and 'tolerance' in tc:
                tolerance_config = tc
            elif isinstance(tc, dict) and 'model' in tc:
                tolerance_config = {'tolerance': tc}
            else:
                tolerance_config = tc
        elif use_calibrated:
            tolerance_config = _load_calibrated_tolerance_config() or {}
            if tolerance_config:
                _calibrated_source = _CALIBRATED_PARAMS_PATH
            else:
                _calibrated_source = None
        else:
            tolerance_config = {}

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

        # Check for tensor engine or GPU request in payload
        if payload.get('tensor_engine') or payload.get('gpu') or payload.get('backend') == 'tensor' or payload.get('engine') == 'tensor':
            try:
                import tensor_simulation
            except ImportError:
                from src import tensor_simulation

            device = 'cuda' if payload.get('gpu') else payload.get('device', 'auto')
            proto = tensor_simulation.TensorProtocolConfig(
                compounds=protocol.compounds,
                doses=protocol.doses,
                frequencies=[float(f) for f in protocol.frequencies],
                duration_days=duration_days,
            )
            cohort_in = payload.get('cohort', 'standard')
            summary = tensor_simulation.run_tensor_simulation(
                total_patients=n_patients,
                protocol=proto,
                cohort=cohort_in,
                chunk_size=payload.get('chunk_size', 250000),
                device=device,
                seed=seed,
                verbose=payload.get('verbose', False),
            )
            res_dict = summary.to_dict() if hasattr(summary, 'to_dict') else dict(summary)
            runner.close()
            return {'ok': True, 'result': {'operation': 'simulate', 'engine': 'tensor', **res_dict}, **res_dict}

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
        runner.close()
        # Return both wrapped (new) and flat (legacy) keys for backward compatibility
        return {'ok': True, 'result': {'operation': 'simulate', **safe}, **safe}

    except Exception as exc:  # pylint: disable=broad-except
        return {'ok': False, 'error': str(exc), 'traceback': traceback.format_exc()}


# ---------------------------------------------------------------------------
# Standalone entrypoint
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    sys.exit(run_cli(None))
