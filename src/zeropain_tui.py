#!/usr/bin/env python3
"""
ZeroPain TUI - Terminal User Interface
Interactive interface for compound selection, optimization, and simulation
"""

import sys
import os
from typing import List, Dict, Optional, Tuple
import json

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.tree import Tree
    from rich.text import Text
    from rich.columns import Columns
    from rich import box
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: rich library not available. Install with: pip install rich")

from opioid_analysis_tools import CompoundDatabase, CompoundProfile
from opioid_optimization_framework import ProtocolOptimizer, ProtocolConfig, run_local_optimization
from patient_simulation_100k import PopulationSimulation, PatientGenerator


class ZeroPainTUI:
    """Interactive Terminal User Interface for ZeroPain"""

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.db = CompoundDatabase()
        self.custom_compounds_file = 'custom_compounds.json'
        self.load_custom_compounds()
        self.use_intel_acceleration = False

    def load_custom_compounds(self):
        """Load custom compounds from file"""
        if os.path.exists(self.custom_compounds_file):
            self.db.import_from_json(self.custom_compounds_file)

    def save_custom_compounds(self):
        """Save custom compounds to file"""
        self.db.export_to_json(self.custom_compounds_file)

    def run(self):
        """Main TUI loop"""
        if not RICH_AVAILABLE:
            self.run_simple_menu()
            return

        self.show_banner()

        while True:
            self.console.print()
            choice = self.show_main_menu()

            if choice == '1':
                self.browse_compounds_menu()
            elif choice == '2':
                self.compound_comparison_menu()
            elif choice == '3':
                self.custom_compound_menu()
            elif choice == '4':
                self.optimization_menu()
            elif choice == '5':
                self.simulation_menu()
            elif choice == '6':
                self.settings_menu()
            elif choice == '7':
                self.export_menu()
            elif choice == 'q':
                self.console.print("\n[bold green]Thank you for using ZeroPain![/bold green]")
                break
            else:
                self.console.print("[red]Invalid choice. Please try again.[/red]")

    def show_banner(self):
        """Display welcome banner"""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  ███████╗███████╗██████╗  ██████╗     ██████╗  █████╗ ██╗███╗   ██╗
║  ╚══███╔╝██╔════╝██╔══██╗██╔═══██╗    ██╔══██╗██╔══██╗██║████╗  ██║
║    ███╔╝ █████╗  ██████╔╝██║   ██║    ██████╔╝███████║██║██╔██╗ ██║
║   ███╔╝  ██╔══╝  ██╔══██╗██║   ██║    ██╔═══╝ ██╔══██║██║██║╚██╗██║
║  ███████╗███████╗██║  ██║╚██████╔╝    ██║     ██║  ██║██║██║ ╚████║
║  ╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝     ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝
║                                                              ║
║           Therapeutics Framework - TUI v3.0                 ║
║        Zero Addiction • Zero Tolerance • Zero Withdrawal    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """
        self.console.print(banner, style="bold cyan")

    def show_main_menu(self) -> str:
        """Display main menu and get user choice"""
        menu = Panel(
            "[1] Browse Compounds\n"
            "[2] Compare Compounds\n"
            "[3] Custom Compound Builder\n"
            "[4] Protocol Optimization\n"
            "[5] Patient Simulation\n"
            "[6] Settings\n"
            "[7] Export Data\n"
            "[q] Quit",
            title="[bold cyan]Main Menu[/bold cyan]",
            border_style="cyan"
        )
        self.console.print(menu)

        choice = Prompt.ask("Select an option", default="1")
        return choice

    def browse_compounds_menu(self):
        """Browse available compounds"""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Compound Database ═══[/bold cyan]\n")

        # Create table
        table = Table(title="Available Compounds", box=box.ROUNDED, show_lines=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Ki (orth)", justify="right")
        table.add_column("Ki (allo1)", justify="right")
        table.add_column("G-bias", justify="right")
        table.add_column("β-arr", justify="right")
        table.add_column("Bias Ratio", justify="right", style="green")
        table.add_column("t½", justify="right")
        table.add_column("Safety", justify="right", style="yellow")
        table.add_column("Type", style="magenta")

        # Add compounds
        all_compounds = self.db.list_compounds()
        for name in sorted(all_compounds):
            compound = self.db.get_compound(name)

            ki_orth = f"{compound.ki_orthosteric:.1f}" if compound.ki_orthosteric != float('inf') else "∞"
            ki_allo1 = f"{compound.ki_allosteric1:.1f}" if compound.ki_allosteric1 != float('inf') else "∞"

            bias_ratio = compound.get_bias_ratio()
            bias_str = f"{bias_ratio:.1f}x" if bias_ratio != float('inf') else "∞"

            safety = compound.calculate_safety_score()

            compound_type = "Custom" if name in self.db.custom_compounds else "Standard"

            table.add_row(
                name,
                ki_orth,
                ki_allo1,
                f"{compound.g_protein_bias:.1f}",
                f"{compound.beta_arrestin_bias:.2f}",
                bias_str,
                f"{compound.t_half:.1f}h",
                f"{safety:.1f}",
                compound_type
            )

        self.console.print(table)

        # Filter options
        self.console.print("\n[bold]Filter Options:[/bold]")
        self.console.print("  [cyan]1[/cyan] Filter by Ki range")
        self.console.print("  [cyan]2[/cyan] Filter by safety score")
        self.console.print("  [cyan]3[/cyan] View compound details")
        self.console.print("  [cyan]Enter[/cyan] Back to main menu")

        choice = Prompt.ask("Select option", default="")

        if choice == '1':
            self.filter_by_ki()
        elif choice == '2':
            self.filter_by_safety()
        elif choice == '3':
            self.view_compound_details()

    def filter_by_ki(self):
        """Filter compounds by Ki value"""
        site = Prompt.ask(
            "Binding site",
            choices=["orthosteric", "allosteric1", "allosteric2"],
            default="orthosteric"
        )

        ki_min = FloatPrompt.ask("Minimum Ki (nM)", default=0.0)
        ki_max = FloatPrompt.ask("Maximum Ki (nM)", default=1000.0)

        compounds = self.db.filter_by_ki_range(ki_min, ki_max, site)

        if not compounds:
            self.console.print("[yellow]No compounds found in range.[/yellow]")
            return

        table = Table(title=f"Compounds with {site} Ki: {ki_min}-{ki_max} nM")
        table.add_column("Name", style="cyan")
        table.add_column("Ki", justify="right")
        table.add_column("Safety", justify="right")

        for compound in compounds:
            if site == "orthosteric":
                ki = compound.ki_orthosteric
            elif site == "allosteric1":
                ki = compound.ki_allosteric1
            else:
                ki = compound.ki_allosteric2

            table.add_row(
                compound.name,
                f"{ki:.2f} nM",
                f"{compound.calculate_safety_score():.1f}"
            )

        self.console.print(table)
        Prompt.ask("\nPress Enter to continue")

    def filter_by_safety(self):
        """Filter compounds by safety score"""
        min_score = FloatPrompt.ask("Minimum safety score", default=70.0)

        compounds = self.db.filter_by_safety(min_score)

        if not compounds:
            self.console.print("[yellow]No compounds found above threshold.[/yellow]")
            return

        table = Table(title=f"Compounds with Safety ≥ {min_score}")
        table.add_column("Name", style="cyan")
        table.add_column("Safety Score", justify="right", style="green")
        table.add_column("Bias Ratio", justify="right")

        for compound in sorted(compounds, key=lambda c: c.calculate_safety_score(), reverse=True):
            table.add_row(
                compound.name,
                f"{compound.calculate_safety_score():.1f}",
                f"{compound.get_bias_ratio():.1f}x"
            )

        self.console.print(table)
        Prompt.ask("\nPress Enter to continue")

    def view_compound_details(self):
        """View detailed compound information"""
        compounds = self.db.list_compounds()
        name = Prompt.ask("Compound name", choices=compounds)

        compound = self.db.get_compound(name)

        # Create detailed view
        details = f"""
[bold cyan]{compound.name}[/bold cyan]

[bold]Binding Affinities (Ki):[/bold]
  Orthosteric:  {compound.ki_orthosteric:.2f} nM
  Allosteric 1: {compound.ki_allosteric1:.2f} nM
  Allosteric 2: {compound.ki_allosteric2:.2f} nM

[bold]Signaling Bias:[/bold]
  G-protein:    {compound.g_protein_bias:.2f}x
  β-arrestin:   {compound.beta_arrestin_bias:.2f}x
  Bias Ratio:   {compound.get_bias_ratio():.1f}x

[bold]Pharmacokinetics:[/bold]
  Half-life:        {compound.t_half:.1f} hours
  Bioavailability:  {compound.bioavailability*100:.1f}%

[bold]Functional Properties:[/bold]
  Intrinsic Activity: {compound.intrinsic_activity:.2f}
  Tolerance Rate:     {compound.tolerance_rate:.2f}
  Prevents Withdrawal: {'Yes' if compound.prevents_withdrawal else 'No'}
  Reverses Tolerance:  {'Yes' if compound.reverses_tolerance else 'No'}

[bold]Safety Assessment:[/bold]
  Safety Score: [green]{compound.calculate_safety_score():.1f}/100[/green]
        """

        panel = Panel(details, title=f"[bold]{compound.name}[/bold]", border_style="cyan")
        self.console.print(panel)

        Prompt.ask("\nPress Enter to continue")

    def compound_comparison_menu(self):
        """Compare multiple compounds"""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Compound Comparison ═══[/bold cyan]\n")

        compounds = self.db.list_compounds()
        selected = []

        while True:
            self.console.print(f"\nSelected: {', '.join(selected) if selected else 'None'}")
            name = Prompt.ask(
                "Add compound (or 'done' to compare)",
                choices=compounds + ['done']
            )

            if name == 'done':
                break

            if name not in selected:
                selected.append(name)

        if len(selected) < 2:
            self.console.print("[yellow]Please select at least 2 compounds.[/yellow]")
            return

        # Create comparison table
        table = Table(title="Compound Comparison", box=box.DOUBLE)
        table.add_column("Property", style="cyan")
        for name in selected:
            table.add_column(name, justify="right")

        # Add rows
        properties = [
            ('Ki (orthosteric)', lambda c: f"{c.ki_orthosteric:.1f}" if c.ki_orthosteric != float('inf') else "∞"),
            ('Ki (allosteric1)', lambda c: f"{c.ki_allosteric1:.1f}" if c.ki_allosteric1 != float('inf') else "∞"),
            ('G-protein bias', lambda c: f"{c.g_protein_bias:.2f}x"),
            ('β-arrestin bias', lambda c: f"{c.beta_arrestin_bias:.2f}x"),
            ('Bias Ratio', lambda c: f"{c.get_bias_ratio():.1f}x"),
            ('Half-life', lambda c: f"{c.t_half:.1f}h"),
            ('Bioavailability', lambda c: f"{c.bioavailability*100:.0f}%"),
            ('Intrinsic Activity', lambda c: f"{c.intrinsic_activity:.2f}"),
            ('Tolerance Rate', lambda c: f"{c.tolerance_rate:.2f}"),
            ('Safety Score', lambda c: f"{c.calculate_safety_score():.1f}"),
        ]

        for prop_name, prop_func in properties:
            row = [prop_name]
            for name in selected:
                compound = self.db.get_compound(name)
                row.append(prop_func(compound))
            table.add_row(*row)

        self.console.print("\n")
        self.console.print(table)

        Prompt.ask("\nPress Enter to continue")

    def custom_compound_menu(self):
        """Custom compound builder"""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Custom Compound Builder ═══[/bold cyan]\n")

        self.console.print("Build your own compound profile\n")

        name = Prompt.ask("Compound name")

        # Check if already exists
        if self.db.get_compound(name):
            if not Confirm.ask(f"Compound '{name}' exists. Overwrite?"):
                return

        self.console.print("\n[bold]Binding Affinities (enter 'inf' for inactive site):[/bold]")
        ki_orth = self._prompt_float_or_inf("Ki orthosteric (nM)", 50.0)
        ki_allo1 = self._prompt_float_or_inf("Ki allosteric1 (nM)", float('inf'))
        ki_allo2 = self._prompt_float_or_inf("Ki allosteric2 (nM)", float('inf'))

        self.console.print("\n[bold]Signaling Bias:[/bold]")
        g_bias = FloatPrompt.ask("G-protein bias", default=1.0)
        beta_bias = FloatPrompt.ask("β-arrestin bias", default=1.0)

        self.console.print("\n[bold]Pharmacokinetics:[/bold]")
        t_half = FloatPrompt.ask("Half-life (hours)", default=6.0)
        bioavail = FloatPrompt.ask("Bioavailability (0-1)", default=0.7)

        self.console.print("\n[bold]Functional Properties:[/bold]")
        intrinsic = FloatPrompt.ask("Intrinsic activity (0-1)", default=0.5)
        tolerance_rate = FloatPrompt.ask("Tolerance rate (0-1)", default=0.3)

        self.console.print("\n[bold]Special Properties:[/bold]")
        prevents_withdrawal = Confirm.ask("Prevents withdrawal?", default=False)
        reverses_tolerance = Confirm.ask("Reverses tolerance?", default=False)

        # Create compound
        compound = CompoundProfile(
            name=name,
            ki_orthosteric=ki_orth,
            ki_allosteric1=ki_allo1,
            ki_allosteric2=ki_allo2,
            g_protein_bias=g_bias,
            beta_arrestin_bias=beta_bias,
            t_half=t_half,
            bioavailability=bioavail,
            intrinsic_activity=intrinsic,
            tolerance_rate=tolerance_rate,
            prevents_withdrawal=prevents_withdrawal,
            reverses_tolerance=reverses_tolerance
        )

        # Show summary
        safety = compound.calculate_safety_score()
        bias_ratio = compound.get_bias_ratio()

        summary = f"""
[bold]Compound Created: {name}[/bold]

Safety Score: [{'green' if safety >= 70 else 'yellow' if safety >= 50 else 'red'}]{safety:.1f}/100[/]
Bias Ratio: {bias_ratio:.1f}x
        """

        self.console.print(Panel(summary, border_style="green"))

        if Confirm.ask("Save this compound?", default=True):
            self.db.add_custom_compound(compound)
            self.save_custom_compounds()
            self.console.print("[green]✓ Compound saved![/green]")

    def _prompt_float_or_inf(self, prompt: str, default: float) -> float:
        """Prompt for float or infinity"""
        while True:
            value = Prompt.ask(prompt, default=str(default) if default != float('inf') else 'inf')
            if value.lower() in ['inf', 'infinity', '∞']:
                return float('inf')
            try:
                return float(value)
            except ValueError:
                self.console.print("[red]Invalid number. Try again.[/red]")

    def optimization_menu(self):
        """Protocol optimization"""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Protocol Optimization ═══[/bold cyan]\n")

        # Select compounds
        compounds_list = self.db.list_compounds()
        selected = []

        self.console.print("Select compounds for protocol (min 1, max 5):\n")

        for i, name in enumerate(compounds_list[:15], 1):  # Show first 15
            compound = self.db.get_compound(name)
            safety = compound.calculate_safety_score()
            self.console.print(f"  [{i:2d}] {name:20s} (Safety: {safety:.0f})")

        self.console.print("\nEnter compound numbers separated by commas (e.g., 1,2,3)")
        choices = Prompt.ask("Compounds", default="1,2,3")

        for choice in choices.split(','):
            try:
                idx = int(choice.strip()) - 1
                if 0 <= idx < len(compounds_list):
                    selected.append(compounds_list[idx])
            except ValueError:
                pass

        if not selected:
            self.console.print("[red]No valid compounds selected.[/red]")
            return

        self.console.print(f"\nSelected: {', '.join(selected)}")

        # Configuration
        n_patients = IntPrompt.ask("Virtual patients", default=1000)
        max_iterations = IntPrompt.ask("Max iterations", default=50)

        # Run optimization
        self.console.print("\n[bold]Starting optimization...[/bold]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Optimizing...", total=None)

            result = run_local_optimization(
                selected,
                n_patients=n_patients,
                max_iterations=max_iterations,
                use_intel=self.use_intel_acceleration
            )

        # Display results
        self._display_optimization_results(result)

    def _display_optimization_results(self, result):
        """Display optimization results"""
        # Create results table
        table = Table(title="Optimal Protocol", box=box.DOUBLE)
        table.add_column("Compound", style="cyan")
        table.add_column("Dose (mg)", justify="right")
        table.add_column("Frequency", justify="center")

        freq_map = {1: 'QD', 2: 'BID', 3: 'TID', 4: 'QID'}

        for compound, dose, freq in zip(
            result.optimal_protocol.compounds,
            result.optimal_protocol.doses,
            result.optimal_protocol.frequencies
        ):
            freq_str = freq_map.get(int(freq), f'{int(freq)}x/day')
            table.add_row(compound, f"{dose:.2f}", freq_str)

        self.console.print("\n")
        self.console.print(table)

        # Metrics
        metrics = Table(title="Performance Metrics", box=box.ROUNDED)
        metrics.add_column("Metric", style="cyan")
        metrics.add_column("Value", justify="right")
        metrics.add_column("Target", justify="right", style="dim")

        metrics_data = [
            ("Success Rate", f"{result.success_rate*100:.2f}%", ">70%", result.success_rate >= 0.70),
            ("Tolerance Rate", f"{result.tolerance_rate*100:.2f}%", "<5%", result.tolerance_rate < 0.05),
            ("Addiction Rate", f"{result.addiction_rate*100:.2f}%", "<3%", result.addiction_rate < 0.03),
            ("Withdrawal Rate", f"{result.withdrawal_rate*100:.2f}%", "0%", result.withdrawal_rate == 0.0),
            ("Safety Score", f"{result.safety_score:.2f}", ">70", result.safety_score > 70),
            ("Therapeutic Window", f"{result.therapeutic_window:.2f}x", ">5x", result.therapeutic_window > 5),
        ]

        for metric, value, target, meets_target in metrics_data:
            style = "green" if meets_target else "yellow"
            metrics.add_row(metric, f"[{style}]{value}[/]", target)

        self.console.print("\n")
        self.console.print(metrics)

        self.console.print(f"\n[dim]Computation time: {result.computation_time:.2f}s[/dim]")

        # Save option
        if Confirm.ask("\nSave protocol to file?", default=True):
            filename = Prompt.ask("Filename", default="optimal_protocol.json")
            self._save_protocol(result.optimal_protocol, filename)
            self.console.print(f"[green]✓ Saved to {filename}[/green]")

        Prompt.ask("\nPress Enter to continue")

    def simulation_menu(self):
        """Patient simulation"""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Patient Simulation ═══[/bold cyan]\n")

        # Protocol selection
        self.console.print("[bold]Protocol Source:[/bold]")
        self.console.print("  [1] Use default protocol (SR-17018 + SR-14968 + Oxycodone)")
        self.console.print("  [2] Load from file")
        self.console.print("  [3] Create custom protocol")

        choice = Prompt.ask("Select option", choices=['1', '2', '3'], default='1')

        if choice == '1':
            protocol = ProtocolConfig(
                compounds=['SR-17018', 'SR-14968', 'Oxycodone'],
                doses=[16.17, 25.31, 5.07],
                frequencies=[2, 1, 4]
            )
        elif choice == '2':
            filename = Prompt.ask("Protocol filename")
            protocol = self._load_protocol(filename)
            if not protocol:
                return
        else:
            protocol = self._create_custom_protocol()
            if not protocol:
                return

        # Simulation parameters
        n_patients = IntPrompt.ask("Number of patients", default=10000)
        duration = IntPrompt.ask("Duration (days)", default=90)

        # Run simulation
        self.console.print("\n[bold]Running simulation...[/bold]")

        simulation = PopulationSimulation(self.db, use_multiprocessing=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Simulating...", total=None)

            results = simulation.run_simulation(
                protocol,
                n_patients=n_patients,
                duration_days=duration
            )

        # Display results
        self._display_simulation_results(results, protocol)

    def _display_simulation_results(self, results: Dict, protocol: ProtocolConfig):
        """Display simulation results"""
        # Protocol summary
        proto_table = Table(title="Protocol", box=box.ROUNDED)
        proto_table.add_column("Compound")
        proto_table.add_column("Dose", justify="right")
        proto_table.add_column("Frequency")

        for compound, dose, freq in zip(protocol.compounds, protocol.doses, protocol.frequencies):
            proto_table.add_row(compound, f"{dose:.2f} mg", f"{int(freq)}x/day")

        self.console.print("\n")
        self.console.print(proto_table)

        # Primary outcomes
        outcomes = Table(title=f"Primary Outcomes (n={results['n_patients']:,})", box=box.DOUBLE)
        outcomes.add_column("Outcome", style="cyan")
        outcomes.add_column("Rate", justify="right")
        outcomes.add_column("Status", justify="center")

        outcome_data = [
            ("Treatment Success", results['success_rate'], 0.70, True),
            ("Tolerance Development", results['tolerance_rate'], 0.05, False),
            ("Addiction Signs", results['addiction_rate'], 0.03, False),
            ("Withdrawal Symptoms", results['withdrawal_rate'], 0.01, False),
        ]

        for outcome, rate, threshold, higher_better in outcome_data:
            if higher_better:
                status = "✓" if rate >= threshold else "⚠"
                color = "green" if rate >= threshold else "yellow"
            else:
                status = "✓" if rate <= threshold else "⚠"
                color = "green" if rate <= threshold else "yellow"

            outcomes.add_row(outcome, f"[{color}]{rate*100:.2f}%[/]", status)

        self.console.print("\n")
        self.console.print(outcomes)

        # Clinical metrics
        clinical = Table(title="Clinical Metrics", box=box.ROUNDED)
        clinical.add_column("Metric", style="cyan")
        clinical.add_column("Mean", justify="right")
        clinical.add_column("Std Dev", justify="right", style="dim")

        clinical.add_row(
            "Pain Score (0-10)",
            f"{results['avg_pain_score']:.2f}",
            f"±{results['pain_score_std']:.2f}"
        )
        clinical.add_row(
            "Analgesia",
            f"{results['avg_analgesia']*100:.1f}%",
            f"±{results['analgesia_std']*100:.1f}%"
        )
        clinical.add_row(
            "Side Effects",
            f"{results['avg_side_effects']*100:.1f}%",
            ""
        )
        clinical.add_row(
            "Quality of Life",
            f"{results['avg_quality_of_life']*100:.1f}%",
            f"±{results['qol_std']*100:.1f}%"
        )

        self.console.print("\n")
        self.console.print(clinical)

        self.console.print(f"\n[dim]Computation time: {results['computation_time']:.2f}s[/dim]")

        Prompt.ask("\nPress Enter to continue")

    def _create_custom_protocol(self) -> Optional[ProtocolConfig]:
        """Create custom protocol interactively"""
        compounds = []
        doses = []
        frequencies = []

        available = self.db.list_compounds()

        while len(compounds) < 5:
            self.console.print(f"\nCompounds selected: {len(compounds)}/5")
            name = Prompt.ask(
                "Add compound (or 'done')",
                choices=available + ['done']
            )

            if name == 'done':
                break

            dose = FloatPrompt.ask(f"Dose for {name} (mg)", default=10.0)
            freq = IntPrompt.ask(f"Frequency (doses/day)", default=2)

            compounds.append(name)
            doses.append(dose)
            frequencies.append(freq)

        if not compounds:
            self.console.print("[yellow]No compounds selected.[/yellow]")
            return None

        return ProtocolConfig(
            compounds=compounds,
            doses=doses,
            frequencies=frequencies
        )

    def settings_menu(self):
        """Settings menu"""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Settings ═══[/bold cyan]\n")

        current_intel = "Enabled" if self.use_intel_acceleration else "Disabled"
        self.console.print(f"Intel NPU/GPU Acceleration: [{current_intel}]")

        if Confirm.ask("Toggle Intel acceleration?"):
            self.use_intel_acceleration = not self.use_intel_acceleration
            status = "enabled" if self.use_intel_acceleration else "disabled"
            self.console.print(f"[green]Intel acceleration {status}[/green]")

        Prompt.ask("\nPress Enter to continue")

    def export_menu(self):
        """Export data menu"""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Export Data ═══[/bold cyan]\n")

        self.console.print("[1] Export compound database to JSON")
        self.console.print("[2] Export custom compounds only")
        self.console.print("[3] Back")

        choice = Prompt.ask("Select option", choices=['1', '2', '3'])

        if choice == '1':
            filename = Prompt.ask("Filename", default="compound_database.json")
            self.db.export_to_json(filename)
            self.console.print(f"[green]✓ Exported to {filename}[/green]")
        elif choice == '2':
            filename = Prompt.ask("Filename", default="custom_compounds.json")
            self.save_custom_compounds()
            self.console.print(f"[green]✓ Exported to {filename}[/green]")

    def _save_protocol(self, protocol: ProtocolConfig, filename: str):
        """Save protocol to JSON file"""
        with open(filename, 'w') as f:
            json.dump(protocol.to_dict(), f, indent=2)

    def _load_protocol(self, filename: str) -> Optional[ProtocolConfig]:
        """Load protocol from JSON file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            return ProtocolConfig(**data)
        except Exception as e:
            self.console.print(f"[red]Error loading protocol: {e}[/red]")
            return None

    def run_simple_menu(self):
        """Fallback simple menu without rich"""
        print("\n" + "="*60)
        print("ZeroPain TUI - Simple Mode")
        print("="*60)
        print("Note: Install 'rich' for full TUI experience: pip install rich")
        print("\nBasic functionality available through Python imports.")
        print("See README for examples.")


if __name__ == '__main__':
    tui = ZeroPainTUI()
    tui.run()
