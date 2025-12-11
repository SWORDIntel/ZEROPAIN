#!/usr/bin/env python3
"""
ZeroPain Pipeline Orchestrator
Main entry point for running the complete pipeline locally
"""

import sys
import argparse
import os
from typing import List, Optional, Dict
import json
from pathlib import Path

# Import core modules
from utils.dependency_bootstrap import ensure_dependencies

ensure_dependencies(["rich", "requests", "matplotlib"])

from opioid_analysis_tools import CompoundDatabase, CompoundProfile, CompoundAnalyzer
from pipeline.distributed_runner import DistributedRunner
from utils.experiment_tracking import ExperimentTracker
from opioid_optimization_framework import (
    ProtocolOptimizer, ProtocolConfig, run_local_optimization, OptimizationResult
)
from patient_simulation_100k import (
    PopulationSimulation,
    PatientGenerationConfig,
    run_100k_simulation,
)
from zeropain_tui import ZeroPainTUI
from pkpd_calibration import (
    calibrate_pkpd,
    load_pkpd_config,
)
from scenarios import parse_cohort_spec, build_generation_config, scenario_defaults
from tolerance_models import (
    make_tolerance_model,
    make_withdrawal_model,
    ToleranceState,
    WithdrawalState,
)


def _load_structured_config(path: Optional[str]) -> Dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("r") as f:
            if path.endswith(".json"):
                return json.load(f)
            try:
                import yaml  # type: ignore

                return yaml.safe_load(f) or {}
            except Exception:
                return {}
    except Exception:
        return {}


class ZeroPainPipeline:
    """Main pipeline orchestrator"""

    def __init__(self, use_intel: bool = False, verbose: bool = True, backend: str = 'local', checkpoint_dir: str = 'runs', run_id: Optional[str] = None, resume: bool = True, batch_size: int = 256, tracker: Optional[ExperimentTracker] = None):
        self.use_intel = use_intel
        self.verbose = verbose
        self.db = CompoundDatabase()
        self.analyzer = CompoundAnalyzer(self.db)
        self.tracker = tracker or ExperimentTracker(base_dir=checkpoint_dir, run_id=run_id)
        self.tracker.upsert_metadata({
            "backend": backend,
            "resume": resume,
            "batch_size": batch_size,
        })
        self.runner = DistributedRunner(
            backend=backend,
            checkpoint_dir=checkpoint_dir,
            run_id=self.tracker.run_id,
            resume=resume,
            num_workers=None,
        )
        self.batch_size = batch_size
        self.resume = resume

        # Load custom compounds if available
        custom_file = 'custom_compounds.json'
        if os.path.exists(custom_file):
            self.db.import_from_json(custom_file)
            if self.verbose:
                print(f"✓ Loaded custom compounds from {custom_file}")

        if self.verbose:
            print(f"Run ID: {self.tracker.run_id}")

    def run_analysis(self, compound_names: List[str]) -> Dict:
        """Run compound analysis"""
        if self.verbose:
            print("\n" + "="*60)
            print("COMPOUND ANALYSIS")
            print("="*60)

        results = {}

        for name in compound_names:
            compound = self.db.get_compound(name)
            if not compound:
                print(f"⚠ Compound '{name}' not found")
                continue

            safety = compound.calculate_safety_score()
            bias_ratio = compound.get_bias_ratio()

            results[name] = {
                'safety_score': safety,
                'bias_ratio': bias_ratio,
                'ki_orthosteric': compound.ki_orthosteric,
                'ki_allosteric1': compound.ki_allosteric1,
                't_half': compound.t_half,
                'bioavailability': compound.bioavailability,
                'g_protein_bias': compound.g_protein_bias,
                'beta_arrestin_bias': compound.beta_arrestin_bias
            }

            if self.verbose:
                print(f"\n{name}:")
                print(f"  Safety Score:    {safety:.1f}/100")
                print(f"  Bias Ratio:      {bias_ratio:.1f}x")
                print(f"  Ki (orthosteric): {compound.ki_orthosteric:.1f} nM")
                print(f"  Half-life:       {compound.t_half:.1f} hours")

        return results

    def run_pkpd_calibration(self, config_path: Optional[str] = None, observations_path: Optional[str] = None) -> Dict:
        """Run PK/PD calibration (MAP) with optional observations."""
        if not config_path:
            return {"skipped": True, "reason": "no_config"}

        if self.verbose:
            print("\n" + "="*60)
            print("PK/PD CALIBRATION")
            print("="*60)
            print(f"Config: {config_path}")

        cfg = load_pkpd_config(config_path)
        observations = {}
        if observations_path and os.path.exists(observations_path):
            with open(observations_path, "r") as f:
                observations = json.load(f)

        result = calibrate_pkpd(cfg, observations)
        self.tracker.log_artifact("pkpd_calibration.json", result)
        return result

    def run_optimization(self,
                        compounds: List[str],
                        n_patients: int = 1000,
                        max_iterations: int = 100,
                        output_file: Optional[str] = None) -> OptimizationResult:
        """Run protocol optimization"""
        if self.verbose:
            print("\n" + "="*60)
            print("PROTOCOL OPTIMIZATION")
            print("="*60)
            print(f"\nCompounds: {', '.join(compounds)}")
            print(f"Virtual patients: {n_patients:,}")
            print(f"Max iterations: {max_iterations}")
            print(f"Intel acceleration: {'Enabled' if self.use_intel else 'Disabled'}")

        result = run_local_optimization(
            compounds,
            n_patients=n_patients,
            max_iterations=max_iterations,
            use_intel=self.use_intel
        )

        if self.verbose:
            self._print_optimization_results(result)

        if output_file:
            self._save_optimization_results(result, output_file)
            self.tracker.log_artifact('optimization_results.json', result.optimal_protocol.to_dict())
            if self.verbose:
                print(f"\n✓ Results saved to {output_file}")

        self.tracker.log_metrics('optimization', {
            'success_rate': result.success_rate,
            'tolerance_rate': result.tolerance_rate,
            'addiction_rate': result.addiction_rate,
            'withdrawal_rate': result.withdrawal_rate,
            'safety_score': result.safety_score,
            'therapeutic_window': result.therapeutic_window,
            'iterations': result.iterations,
            'computation_time': result.computation_time,
        })

        return result

    def run_simulation(self,
                      protocol: ProtocolConfig,
                      n_patients: int = 100000,
                      duration_days: int = 90,
                      generation_config: Optional[PatientGenerationConfig] = None,
                      output_file: Optional[str] = None,
                      scenario_id: Optional[str] = None,
                      cohort_spec: Optional[str] = None,
                      tolerance_config: Optional[Dict] = None) -> Dict:
        """Run patient simulation"""
        if self.verbose:
            print("\n" + "="*60)
            print("PATIENT SIMULATION")
            print("="*60)
            print(f"\nProtocol:")
            for compound, dose, freq in zip(protocol.compounds, protocol.doses, protocol.frequencies):
                print(f"  {compound:20s}: {dose:6.2f} mg, {int(freq)}x/day")
            print(f"\nPatients: {n_patients:,}")
            print(f"Duration: {duration_days} days")

        simulation = PopulationSimulation(self.db, use_multiprocessing=self.runner.backend == 'local')

        if generation_config is None and cohort_spec:
            cohort = parse_cohort_spec(cohort_spec)
            generation_config = build_generation_config(cohort)
            n_patients = cohort.n
        if generation_config and generation_config.population_size:
            n_patients = generation_config.population_size

        results = simulation.run_simulation(
            protocol,
            n_patients=n_patients,
            duration_days=duration_days,
            generation_config=generation_config,
            runner=self.runner,
            checkpoint_stage='simulation',
            batch_size=self.batch_size
        )

        # Tolerance projection (lightweight, not replacing core simulator)
        if tolerance_config:
            tol_model = make_tolerance_model(tolerance_config.get("tolerance", {}))
            wd_model = make_withdrawal_model(tolerance_config.get("tolerance", {}))
            tol_state = ToleranceState(level=0.0, ceiling=tolerance_config.get("tolerance", {}).get("max_factor", 3.0))
            wd_state = WithdrawalState(severity=0.0, onset_delay_days=2.0)
            tol_state = tol_model.update(
                state=tol_state,
                exposure=sum(protocol.doses) * duration_days,
                dt_days=1.0,
            )
            wd_state = wd_model.update(
                state=wd_state,
                abstinence_metric=0.0,
                dt_days=1.0,
            )
            results["tolerance_projection"] = {
                "model": tolerance_config.get("tolerance", {}).get("model", "sigmoid"),
                "level": getattr(tol_state, "level", 0.0),
                "ceiling": getattr(tol_state, "ceiling", 0.0),
                "withdrawal_severity": getattr(wd_state, "severity", 0.0),
            }

        if self.verbose:
            self._print_simulation_results(results)

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            if self.verbose:
                print(f"\n✓ Results saved to {output_file}")

        self.tracker.log_metrics('simulation', {
            'success_rate': results.get('success_rate'),
            'tolerance_rate': results.get('tolerance_rate'),
            'addiction_rate': results.get('addiction_rate'),
            'withdrawal_rate': results.get('withdrawal_rate'),
            'adverse_event_rate': results.get('adverse_event_rate'),
            'avg_pain_score': results.get('avg_pain_score'),
            'avg_analgesia': results.get('avg_analgesia'),
            'avg_side_effects': results.get('avg_side_effects'),
            'avg_g_activation': results.get('avg_g_activation'),
            'avg_beta_activation': results.get('avg_beta_activation'),
            'avg_quality_of_life': results.get('avg_quality_of_life'),
            'computation_time': results.get('computation_time'),
            **{k: v for k, v in results.items() if k.startswith('nt_')},
        })
        self.tracker.upsert_metadata({
            "scenario": scenario_id,
            "cohort_spec": cohort_spec,
        })

        return results

    def run_scenario(self,
                     protocol: ProtocolConfig,
                     scenario_id: str,
                     cohort_spec: Optional[str] = None,
                     duration_days: Optional[int] = None,
                     output_file: Optional[str] = None,
                     tolerance_config: Optional[Dict] = None) -> Dict:
        defaults = scenario_defaults(scenario_id)
        gen_cfg = None
        if cohort_spec:
            cohort = parse_cohort_spec(cohort_spec)
            gen_cfg = build_generation_config(cohort)
            n_patients = cohort.n
        else:
            n_patients = defaults.get("n_patients", 500)

        horizon = duration_days or defaults.get("horizon_days", 30)

        self.tracker.record_config({
            "scenario": scenario_id,
            "cohort_spec": cohort_spec,
            "horizon_days": horizon,
        })

        return self.run_simulation(
            protocol,
            n_patients=n_patients,
            duration_days=horizon,
            generation_config=gen_cfg,
            output_file=output_file,
            scenario_id=scenario_id,
            cohort_spec=cohort_spec,
            tolerance_config=tolerance_config,
        )

    def run_full_pipeline(self,
                         compounds: List[str],
                         n_patients_optimization: int = 1000,
                         n_patients_simulation: int = 100000,
                         max_iterations: int = 100,
                         output_dir: str = 'results') -> Dict:
        """Run complete pipeline: analysis → optimization → simulation"""
        if self.verbose:
            print("\n" + "="*70)
            print("ZEROPAIN FULL PIPELINE")
            print("="*70)

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        self.tracker.record_config({
            'compounds': compounds,
            'n_patients_optimization': n_patients_optimization,
            'n_patients_simulation': n_patients_simulation,
            'max_iterations': max_iterations,
            'use_intel': self.use_intel,
            'backend': self.runner.backend,
            'resume': self.resume,
        })

        # Step 1: Compound Analysis
        analysis_results = self.run_analysis(compounds)

        # Step 2: Protocol Optimization
        opt_result = self.run_optimization(
            compounds,
            n_patients=n_patients_optimization,
            max_iterations=max_iterations,
            output_file=os.path.join(output_dir, 'optimization_results.json')
        )

        # Step 3: Large-scale Simulation
        sim_results = self.run_simulation(
            opt_result.optimal_protocol,
            n_patients=n_patients_simulation,
            output_file=os.path.join(output_dir, 'simulation_results.json')
        )

        # Compile final results
        final_results = {
            'compounds_analyzed': compounds,
            'analysis': analysis_results,
            'optimal_protocol': opt_result.optimal_protocol.to_dict(),
            'optimization_metrics': {
                'success_rate': opt_result.success_rate,
                'tolerance_rate': opt_result.tolerance_rate,
                'addiction_rate': opt_result.addiction_rate,
                'withdrawal_rate': opt_result.withdrawal_rate,
                'safety_score': opt_result.safety_score,
                'therapeutic_window': opt_result.therapeutic_window,
                'computation_time': opt_result.computation_time
            },
            'simulation_metrics': sim_results
        }

        # Save complete results
        final_file = os.path.join(output_dir, 'pipeline_complete.json')
        with open(final_file, 'w') as f:
            json.dump(final_results, f, indent=2)
        self.tracker.log_artifact('pipeline_complete.json', final_results)

        if self.verbose:
            print("\n" + "="*70)
            print("PIPELINE COMPLETE")
            print("="*70)
            print(f"\n✓ All results saved to: {output_dir}/")
            print(f"  - optimization_results.json")
            print(f"  - simulation_results.json")
            print(f"  - pipeline_complete.json")

        return final_results

    def _print_optimization_results(self, result: OptimizationResult):
        """Print optimization results"""
        print("\n" + "-"*60)
        print("OPTIMAL PROTOCOL")
        print("-"*60)

        freq_map = {1: 'QD', 2: 'BID', 3: 'TID', 4: 'QID'}

        for compound, dose, freq in zip(
            result.optimal_protocol.compounds,
            result.optimal_protocol.doses,
            result.optimal_protocol.frequencies
        ):
            freq_str = freq_map.get(int(freq), f'{int(freq)}x/day')
            print(f"  {compound:20s}: {dose:6.2f} mg {freq_str}")

        print("\n" + "-"*60)
        print("PERFORMANCE METRICS")
        print("-"*60)
        print(f"  Success Rate:       {result.success_rate*100:6.2f}% (target: >70%)")
        print(f"  Tolerance Rate:     {result.tolerance_rate*100:6.2f}% (target: <5%)")
        print(f"  Addiction Rate:     {result.addiction_rate*100:6.2f}% (target: <3%)")
        print(f"  Withdrawal Rate:    {result.withdrawal_rate*100:6.2f}% (target: 0%)")
        print(f"  Safety Score:       {result.safety_score:6.2f}")
        print(f"  Therapeutic Window: {result.therapeutic_window:6.2f}x")

        print(f"\n  Computation Time:   {result.computation_time:.2f} seconds")
        print(f"  Iterations:         {result.iterations}")

    def _print_simulation_results(self, results: Dict):
        """Print simulation results"""
        print("\n" + "-"*60)
        print(f"PRIMARY OUTCOMES (n={results['n_patients']:,})")
        print("-"*60)
        print(f"  Treatment Success:     {results['success_rate']*100:6.2f}%")
        print(f"  Tolerance Development: {results['tolerance_rate']*100:6.2f}%")
        print(f"  Addiction Signs:       {results['addiction_rate']*100:6.2f}%")
        print(f"  Withdrawal Symptoms:   {results['withdrawal_rate']*100:6.2f}%")
        print(f"  Adverse Events:        {results['adverse_event_rate']*100:6.2f}%")

        print("\n" + "-"*60)
        print("CLINICAL METRICS")
        print("-"*60)
        print(f"  Average Pain Score:    {results['avg_pain_score']:6.2f} / 10")
        print(f"  Average Analgesia:     {results['avg_analgesia']*100:6.2f}%")
        print(f"  Average Side Effects:  {results['avg_side_effects']*100:6.2f}%")
        print(f"  Quality of Life:       {results['avg_quality_of_life']*100:6.2f}%")

        print(f"\n  Computation Time:      {results['computation_time']:.2f} seconds")

    def _save_optimization_results(self, result: OptimizationResult, filename: str):
        """Save optimization results to JSON"""
        data = {
            'optimal_protocol': result.optimal_protocol.to_dict(),
            'metrics': {
                'success_rate': result.success_rate,
                'tolerance_rate': result.tolerance_rate,
                'addiction_rate': result.addiction_rate,
                'withdrawal_rate': result.withdrawal_rate,
                'safety_score': result.safety_score,
                'therapeutic_window': result.therapeutic_window
            },
            'computation': {
                'iterations': result.iterations,
                'time_seconds': result.computation_time
            }
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)


def main():
    """Main entry point with CLI"""
    parser = argparse.ArgumentParser(
        description='ZeroPain Therapeutics Framework - Pipeline Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch interactive TUI
  python zeropain_pipeline.py --tui

  # Run full pipeline
  python zeropain_pipeline.py --full --compounds SR-17018 SR-14968 Oxycodone

  # Run optimization only
  python zeropain_pipeline.py --optimize --compounds SR-17018 Oxycodone

  # Run simulation with custom protocol
  python zeropain_pipeline.py --simulate --protocol protocol.json

  # Analyze compounds
  python zeropain_pipeline.py --analyze --compounds Morphine Fentanyl Buprenorphine
        """
    )

    parser.add_argument('--tui', action='store_true',
                       help='Launch interactive TUI')
    parser.add_argument('--full', action='store_true',
                       help='Run full pipeline (analysis + optimization + simulation)')
    parser.add_argument('--analyze', action='store_true',
                       help='Run compound analysis only')
    parser.add_argument('--optimize', action='store_true',
                       help='Run protocol optimization only')
    parser.add_argument('--simulate', action='store_true',
                       help='Run patient simulation only')

    parser.add_argument('--compounds', nargs='+',
                       help='Compound names to use')
    parser.add_argument('--protocol', type=str,
                       help='Protocol JSON file for simulation')

    parser.add_argument('--n-patients-opt', type=int, default=1000,
                       help='Number of patients for optimization (default: 1000)')
    parser.add_argument('--n-patients-sim', type=int, default=100000,
                       help='Number of patients for simulation (default: 100000)')
    parser.add_argument('--max-iterations', type=int, default=100,
                       help='Maximum optimization iterations (default: 100)')

    parser.add_argument('--pkpd-config', type=str,
                       help='PK/PD calibration config (YAML/JSON)')
    parser.add_argument('--pkpd-observations', type=str,
                       help='Observations JSON for PK/PD calibration')
    parser.add_argument('--tolerance-config', type=str,
                       help='Tolerance/withdrawal config (YAML/JSON)')
    parser.add_argument('--scenario', type=str,
                       help='Scenario template id (perioperative|chronic|breakthrough)')
    parser.add_argument('--cohort', type=str,
                       help='Cohort spec e.g., "n=200,age=60±10,renal=0.3,seed=42"')
    parser.add_argument('--dosing-policy', type=str, default='fixed',
                       help='Dosing policy (fixed|exposure|toxicity)')

    parser.add_argument('--intel', action='store_true',
                       help='Enable Intel NPU/GPU acceleration')
    parser.add_argument('--output-dir', type=str, default='results',
                       help='Output directory for results (default: results)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress verbose output')
    parser.add_argument('--backend', choices=['local', 'ray', 'dask'], default='local',
                       help='Execution backend for distributed runs (default: local)')
    parser.add_argument('--checkpoint-dir', type=str, default='runs',
                       help='Directory for checkpoints and artifacts (default: runs)')
    parser.add_argument('--run-id', type=str,
                       help='Optional run identifier for resuming a previous run')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                       help='Disable checkpoint resume')
    parser.add_argument('--batch-size', type=int, default=256,
                       help='Batch size for distributed simulation shards (default: 256)')
    parser.set_defaults(resume=True)

    args = parser.parse_args()

    # Launch TUI if requested
    if args.tui:
        tui = ZeroPainTUI()
        tui.run()
        return

    # Require at least one mode
    if not any([args.full, args.analyze, args.optimize, args.simulate, args.pkpd_config]):
        parser.print_help()
        return

    # Create pipeline
    pipeline = ZeroPainPipeline(
        use_intel=args.intel,
        verbose=not args.quiet,
        backend=args.backend,
        checkpoint_dir=args.checkpoint_dir,
        run_id=args.run_id,
        resume=args.resume,
        batch_size=args.batch_size,
    )

    tolerance_cfg = _load_structured_config(args.tolerance_config)

    # Optional PK/PD calibration (can run standalone or before other modes)
    if args.pkpd_config:
        pipeline.run_pkpd_calibration(
            config_path=args.pkpd_config,
            observations_path=args.pkpd_observations,
        )

    # Run requested operations
    if args.full:
        if not args.compounds:
            print("Error: --compounds required for full pipeline")
            return

        pipeline.run_full_pipeline(
            compounds=args.compounds,
            n_patients_optimization=args.n_patients_opt,
            n_patients_simulation=args.n_patients_sim,
            max_iterations=args.max_iterations,
            output_dir=args.output_dir
        )

    elif args.analyze:
        if not args.compounds:
            print("Error: --compounds required for analysis")
            return

        pipeline.run_analysis(args.compounds)

    elif args.optimize:
        if not args.compounds:
            print("Error: --compounds required for optimization")
            return

        output_file = os.path.join(args.output_dir, 'optimization_results.json')
        os.makedirs(args.output_dir, exist_ok=True)

        pipeline.run_optimization(
            compounds=args.compounds,
            n_patients=args.n_patients_opt,
            max_iterations=args.max_iterations,
            output_file=output_file
        )

    elif args.simulate:
        if args.protocol:
            with open(args.protocol, 'r') as f:
                protocol_data = json.load(f)
            protocol = ProtocolConfig(**protocol_data)
        elif args.compounds:
            # Use default dosing
            protocol = ProtocolConfig(
                compounds=args.compounds,
                doses=[10.0] * len(args.compounds),
                frequencies=[2] * len(args.compounds)
            )
        else:
            print("Error: --protocol or --compounds required for simulation")
            return

        output_file = os.path.join(args.output_dir, 'simulation_results.json')
        os.makedirs(args.output_dir, exist_ok=True)

        if args.scenario:
            pipeline.run_scenario(
                protocol=protocol,
                scenario_id=args.scenario,
                cohort_spec=args.cohort,
                duration_days=None,
                output_file=output_file,
                tolerance_config=tolerance_cfg,
            )
        else:
            pipeline.run_simulation(
                protocol=protocol,
                n_patients=args.n_patients_sim,
                output_file=output_file,
                scenario_id=args.scenario,
                cohort_spec=args.cohort,
                tolerance_config=tolerance_cfg,
            )


if __name__ == '__main__':
    main()
