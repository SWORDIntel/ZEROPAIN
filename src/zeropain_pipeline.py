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

# Import core modules
from opioid_analysis_tools import CompoundDatabase, CompoundProfile, CompoundAnalyzer
from opioid_optimization_framework import (
    ProtocolOptimizer, ProtocolConfig, run_local_optimization, OptimizationResult
)
from patient_simulation_100k import PopulationSimulation, run_100k_simulation
from zeropain_tui import ZeroPainTUI


class ZeroPainPipeline:
    """Main pipeline orchestrator"""

    def __init__(self, use_intel: bool = False, verbose: bool = True):
        self.use_intel = use_intel
        self.verbose = verbose
        self.db = CompoundDatabase()
        self.analyzer = CompoundAnalyzer(self.db)

        # Load custom compounds if available
        custom_file = 'custom_compounds.json'
        if os.path.exists(custom_file):
            self.db.import_from_json(custom_file)
            if self.verbose:
                print(f"✓ Loaded custom compounds from {custom_file}")

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
            if self.verbose:
                print(f"\n✓ Results saved to {output_file}")

        return result

    def run_simulation(self,
                      protocol: ProtocolConfig,
                      n_patients: int = 100000,
                      duration_days: int = 90,
                      output_file: Optional[str] = None) -> Dict:
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

        simulation = PopulationSimulation(self.db, use_multiprocessing=True)

        results = simulation.run_simulation(
            protocol,
            n_patients=n_patients,
            duration_days=duration_days
        )

        if self.verbose:
            self._print_simulation_results(results)

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            if self.verbose:
                print(f"\n✓ Results saved to {output_file}")

        return results

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

    parser.add_argument('--intel', action='store_true',
                       help='Enable Intel NPU/GPU acceleration')
    parser.add_argument('--output-dir', type=str, default='results',
                       help='Output directory for results (default: results)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress verbose output')

    args = parser.parse_args()

    # Launch TUI if requested
    if args.tui:
        tui = ZeroPainTUI()
        tui.run()
        return

    # Require at least one mode
    if not any([args.full, args.analyze, args.optimize, args.simulate]):
        parser.print_help()
        return

    # Create pipeline
    pipeline = ZeroPainPipeline(
        use_intel=args.intel,
        verbose=not args.quiet
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

        pipeline.run_simulation(
            protocol=protocol,
            n_patients=args.n_patients_sim,
            output_file=output_file
        )


if __name__ == '__main__':
    main()
