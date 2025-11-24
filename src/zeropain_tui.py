#!/usr/bin/env python3
"""
ZeroPain TUI - Terminal User Interface
Interactive interface for compound selection, optimization, and simulation
"""
from __future__ import annotations

import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from utils.dependency_bootstrap import ensure_dependencies

REQUIRED_PACKAGES = ["rich", "matplotlib", "requests"]
ensure_dependencies(REQUIRED_PACKAGES)

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
    from rich.theme import Theme
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: rich library not available. Install with: pip install rich")

from opioid_analysis_tools import CompoundDatabase, CompoundProfile
from opioid_optimization_framework import ProtocolOptimizer, ProtocolConfig, run_local_optimization
from patient_simulation_100k import (
    PopulationSimulation,
    PatientGenerator,
    PatientGenerationConfig,
    AgeDistribution,
    WeightDistribution,
    MedicationProfile,
)
from pipeline.distributed_runner import DistributedRunner
from utils.experiment_tracking import ExperimentTracker


class ZeroPainTUI:
    """Interactive Terminal User Interface for ZeroPain"""

    def __init__(self):
        self.theme = (
            Theme(
                {
                    "accent": "cyan",
                    "ok": "green",
                    "warn": "yellow",
                    "error": "red",
                    "panel": "bold cyan",
                    "muted": "dim",
                }
            )
            if RICH_AVAILABLE
            else None
        )
        self.console = Console(theme=self.theme) if RICH_AVAILABLE else None
        self.db = CompoundDatabase()
        self.custom_compounds_file = 'custom_compounds.json'
        self.load_custom_compounds()
        self.use_intel_acceleration = False
        self.checkpoint_dir = "runs"
        self.backend = "local"
        self.resume = True
        self.batch_size = 256
        self.current_run_id: Optional[str] = None
        self.tracker: Optional[ExperimentTracker] = None
        self.animations_enabled = True
        self.refresh_hz = 8

    def _progress(self, description: str) -> Progress:
        if not RICH_AVAILABLE:
            raise RuntimeError("Progress UI requires Rich. Please install dependencies.")
        columns = []
        if self.animations_enabled:
            columns.append(SpinnerColumn())
        else:
            columns.append(TextColumn("[cyan]⏳[/cyan]"))
        columns.extend(
            [
                TextColumn("[progress.description]{task.description}"),
                BarColumn(pulse=self.animations_enabled),
                TimeElapsedColumn(),
            ]
        )
        return Progress(
            *columns,
            console=self.console,
            refresh_per_second=self.refresh_hz,
            transient=not self.animations_enabled,
        )

    def load_custom_compounds(self):
        """Load custom compounds from file"""
        if os.path.exists(self.custom_compounds_file):
            self.db.import_from_json(self.custom_compounds_file)

    def save_custom_compounds(self):
        """Save custom compounds to file"""
        self.db.export_to_json(self.custom_compounds_file)

    def _ensure_tracker(self) -> ExperimentTracker:
        """Create or reuse a tracker for this TUI session."""
        if not self.current_run_id:
            self.current_run_id = time.strftime("%Y%m%d-%H%M%S")
        if not self.tracker:
            self.tracker = ExperimentTracker(
                base_dir=self.checkpoint_dir, run_id=self.current_run_id
            )
            self.tracker.append_audit_event("tui_session_started", {"origin": "tui"})
        self.tracker.upsert_metadata(
            {
                "backend": self.backend,
                "resume": self.resume,
                "batch_size": self.batch_size,
            }
        )
        return self.tracker

    def _build_runner(self) -> DistributedRunner:
        tracker = self._ensure_tracker()
        return DistributedRunner(
            backend=self.backend,
            checkpoint_dir=self.checkpoint_dir,
            run_id=tracker.run_id,
            resume=self.resume,
            num_workers=None,
        )

    def _prompt_population_config(self, default_n: int) -> Tuple[int, PatientGenerationConfig]:
        """Collect population knobs including ages and comorbidities."""
        n_patients = IntPrompt.ask("Number of patients", default=default_n)
        customize = Confirm.ask("Customize age/condition distributions?", default=False)

        if not customize:
            return n_patients, PatientGenerationConfig(population_size=n_patients)

        self.console.print("\n[bold cyan]Population Tuning[/bold cyan]")
        min_age = IntPrompt.ask("Minimum age", default=18)
        max_age = IntPrompt.ask("Maximum age", default=85)
        age_alpha = FloatPrompt.ask("Age beta distribution α", default=2.0)
        age_beta = FloatPrompt.ask("Age beta distribution β", default=3.0)

        sex_ratio_male = FloatPrompt.ask("Male proportion (0-1)", default=0.5)

        male_mean = FloatPrompt.ask("Male weight mean (kg)", default=82.0)
        male_std = FloatPrompt.ask("Male weight std", default=15.0)
        female_mean = FloatPrompt.ask("Female weight mean (kg)", default=70.0)
        female_std = FloatPrompt.ask("Female weight std", default=13.0)

        self.console.print("\n[bold]Comorbidity prevalence (0-1)[/bold]")
        comorbidity_defaults = PatientGenerationConfig().comorbidity_prevalence
        comorbidity_prevalence: Dict[str, float] = {}
        for condition, default_rate in comorbidity_defaults.items():
            comorbidity_prevalence[condition] = FloatPrompt.ask(
                f"{condition}", default=default_rate
            )

        self.console.print("\n[bold]Pre-existing medications[/bold]")
        med_defaults = PatientGenerationConfig().pre_existing_medications
        medication_profiles: Dict[str, MedicationProfile] = {}
        for key, med in med_defaults.items():
            prevalence = FloatPrompt.ask(
                f"{med.name} prevalence (0-1)", default=med.prevalence
            )
            metabolism_multiplier = FloatPrompt.ask(
                f"{med.name} metabolism multiplier", default=med.metabolism_multiplier
            )
            sensitivity_multiplier = FloatPrompt.ask(
                f"{med.name} sensitivity multiplier", default=med.sensitivity_multiplier
            )
            analgesia_bonus = FloatPrompt.ask(
                f"{med.name} analgesia bonus", default=med.analgesia_bonus
            )
            side_effect_bias = FloatPrompt.ask(
                f"{med.name} side-effect bias", default=med.side_effect_bias
            )
            baseline_tolerance = FloatPrompt.ask(
                f"{med.name} baseline tolerance", default=med.baseline_tolerance
            )
            medication_profiles[key] = MedicationProfile(
                name=med.name,
                prevalence=prevalence,
                metabolism_multiplier=metabolism_multiplier,
                sensitivity_multiplier=sensitivity_multiplier,
                analgesia_bonus=analgesia_bonus,
                side_effect_bias=side_effect_bias,
                baseline_tolerance=baseline_tolerance,
            )

        pain_alpha = FloatPrompt.ask("Pain severity alpha", default=3.0)
        pain_beta = FloatPrompt.ask("Pain severity beta", default=2.0)
        sensitivity_sigma = FloatPrompt.ask("Receptor sensitivity σ", default=0.3)
        metabolism_sigma = FloatPrompt.ask("Metabolism σ", default=0.25)

        config = PatientGenerationConfig(
            population_size=n_patients,
            age_distribution=AgeDistribution(
                alpha=age_alpha, beta=age_beta, min_age=min_age, max_age=max_age
            ),
            weight_distribution=WeightDistribution(
                male_mean=male_mean,
                male_std=male_std,
                female_mean=female_mean,
                female_std=female_std,
            ),
            comorbidity_prevalence=comorbidity_prevalence,
            pain_alpha=pain_alpha,
            pain_beta=pain_beta,
            sensitivity_sigma=sensitivity_sigma,
            metabolism_sigma=metabolism_sigma,
            pre_existing_medications=medication_profiles,
            sex_ratio_male=sex_ratio_male,
        )
        return n_patients, config

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
                self.run_history_menu()
            elif choice == '8':
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
        self.console.print(
            "[muted]TEMPEST CLASS C theme active — smooth animations are [green]enabled[/green]. "
            "Disable animations or lower refresh in Settings to reduce CPU load.[/muted]"
        )

    def show_main_menu(self) -> str:
        """Display main menu and get user choice"""
        menu = Panel(
            "[1] Browse Compounds\n"
            "[2] Compare Compounds\n"
            "[3] Custom Compound Builder\n"
            "[4] Protocol Optimization\n"
            "[5] Patient Simulation\n"
            "[6] Settings\n"
            "[7] Run Dashboard\n"
            "[8] Export Data\n"
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

[bold]Pharmacological Activities:[/bold]
  {', '.join(compound.pharmacological_activities) if compound.pharmacological_activities else 'Not specified'}
  Notes: {compound.mechanism_notes or 'n/a'}

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

        guidance = """
* Guided flow: choose a template, adjust receptor affinities, PK, and signaling bias.
* Templates: any existing compound in the library or external sources (set ZP_COMPOUND_SOURCES).
* Enter numerical overrides to tweak Ki, bias, and kinetics when the desired compound is absent.
        """
        self.console.print(Markdown(guidance))

        template_hint = Prompt.ask(
            "Template compound (Enter for manual, or type name to preload)", default=""
        )
        base_profile = None
        if template_hint:
            base_profile = self.db.get_compound(template_hint)
            if not base_profile:
                external_profile = self.db.hydrate_from_sources(template_hint)
                if external_profile:
                    base_profile = external_profile
                    self.console.print(
                        f"[green]✓ Imported {template_hint} from external sources for editing.[/green]"
                    )
                else:
                    self.console.print(
                        f"[yellow]No template found for {template_hint}; starting manual build.[/yellow]"
                    )

        name_default = base_profile.name if base_profile else ""
        name = Prompt.ask("Compound name", default=name_default)

        if self.db.get_compound(name):
            if not Confirm.ask(f"Compound '{name}' exists. Overwrite?"):
                return

        def default(val, fallback):
            return val if val is not None else fallback

        self.console.print("\n[bold]Binding Affinities (enter 'inf' for inactive site):[/bold]")
        ki_orth = self._prompt_float_or_inf(
            "Ki orthosteric (nM)", default(base_profile.ki_orthosteric if base_profile else None, 50.0)
        )
        ki_allo1 = self._prompt_float_or_inf(
            "Ki allosteric1 (nM)", default(base_profile.ki_allosteric1 if base_profile else None, float('inf'))
        )
        ki_allo2 = self._prompt_float_or_inf(
            "Ki allosteric2 (nM)", default(base_profile.ki_allosteric2 if base_profile else None, float('inf'))
        )

        self.console.print("\n[bold]Signaling Bias:[/bold]")
        g_bias = FloatPrompt.ask(
            "G-protein bias", default=default(base_profile.g_protein_bias if base_profile else None, 1.0)
        )
        beta_bias = FloatPrompt.ask(
            "β-arrestin bias", default=default(base_profile.beta_arrestin_bias if base_profile else None, 1.0)
        )

        self.console.print("\n[bold]Pharmacokinetics:[/bold]")
        t_half = FloatPrompt.ask(
            "Half-life (hours)", default=default(base_profile.t_half if base_profile else None, 6.0)
        )
        bioavail = FloatPrompt.ask(
            "Bioavailability (0-1)", default=default(base_profile.bioavailability if base_profile else None, 0.7)
        )

        self.console.print("\n[bold]Functional Properties:[/bold]")
        intrinsic = FloatPrompt.ask(
            "Intrinsic activity (0-1)", default=default(base_profile.intrinsic_activity if base_profile else None, 0.5)
        )
        tolerance_rate = FloatPrompt.ask(
            "Tolerance rate (0-1)", default=default(base_profile.tolerance_rate if base_profile else None, 0.3)
        )

        self.console.print("\n[bold]Special Properties:[/bold]")
        prevents_withdrawal = Confirm.ask(
            "Prevents withdrawal?", default=default(base_profile.prevents_withdrawal if base_profile else None, False)
        )
        reverses_tolerance = Confirm.ask(
            "Reverses tolerance?", default=default(base_profile.reverses_tolerance if base_profile else None, False)
        )
        receptor_type = Prompt.ask(
            "Receptor target (MOR/DOR/KOR)",
            choices=["MOR", "DOR", "KOR"],
            default=default(base_profile.receptor_type if base_profile else None, "MOR"),
        )

        activities_default = "".join(
            [", ".join(base_profile.pharmacological_activities)]
        ) if base_profile else ""
        activities_raw = Prompt.ask(
            "Pharmacological activities (comma-separated)",
            default=activities_default,
        )
        pharmacological_activities = [
            a.strip() for a in activities_raw.split(",") if a.strip()
        ]
        mechanism_notes = Prompt.ask(
            "Mechanism notes", default=base_profile.mechanism_notes if base_profile else ""
        )

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
            reverses_tolerance=reverses_tolerance,
            receptor_type=receptor_type,
            pharmacological_activities=pharmacological_activities,
            mechanism_notes=mechanism_notes,
        )

        safety = compound.calculate_safety_score()
        bias_ratio = compound.get_bias_ratio()

        summary = f"""
[bold]Compound Created: {name}[/bold]

Safety Score: [{'green' if safety >= 70 else 'yellow' if safety >= 50 else 'red'}]{safety:.1f}/100[/]
Bias Ratio: {bias_ratio:.1f}x
Template: {template_hint or 'manual'}
        """

        self.console.print(Panel(summary, border_style="green"))

        if Confirm.ask("Save this compound?", default=True):
            self.db.add_custom_compound(compound)
            self.save_custom_compounds()
            self.console.print("[green]✓ Compound saved![/green]")
            tracker = self._ensure_tracker()
            tracker.append_audit_event("compound_saved", {"name": name})

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

        tracker = self._ensure_tracker()
        tracker.record_config(
            {
                "mode": "optimization",
                "compounds": selected,
                "n_patients": n_patients,
                "max_iterations": max_iterations,
                "backend": self.backend,
                "resume": self.resume,
            }
        )

        with self._progress("Optimizing...") as progress:
            task = progress.add_task("Optimizing...", total=None)

            result = run_local_optimization(
                selected,
                n_patients=n_patients,
                max_iterations=max_iterations,
                use_intel=self.use_intel_acceleration
            )

        # Display results
        self._display_optimization_results(result)

        tracker.log_metrics(
            "optimization",
            {
                "success_rate": result.success_rate,
                "tolerance_rate": result.tolerance_rate,
                "addiction_rate": result.addiction_rate,
                "withdrawal_rate": result.withdrawal_rate,
                "safety_score": result.safety_score,
                "therapeutic_window": result.therapeutic_window,
                "iterations": result.iterations,
                "computation_time": result.computation_time,
            },
        )
        tracker.log_artifact(
            "optimization_results.json",
            {
                "optimal_protocol": result.optimal_protocol.to_dict(),
                "metrics": {
                    "success_rate": result.success_rate,
                    "tolerance_rate": result.tolerance_rate,
                    "addiction_rate": result.addiction_rate,
                    "withdrawal_rate": result.withdrawal_rate,
                    "safety_score": result.safety_score,
                    "therapeutic_window": result.therapeutic_window,
                },
            },
        )

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
        n_patients, generation_config = self._prompt_population_config(10000)
        duration = IntPrompt.ask("Duration (days)", default=90)

        # Run simulation
        self.console.print("\n[bold]Running simulation...[/bold]")
        tracker = self._ensure_tracker()
        tracker.record_config(
            {
                "mode": "simulation",
                "n_patients": n_patients,
                "duration_days": duration,
                "age_distribution": generation_config.age_distribution.__dict__,
                "weight_distribution": generation_config.weight_distribution.__dict__,
                "sex_ratio_male": generation_config.sex_ratio_male,
                "comorbidity_prevalence": generation_config.comorbidity_prevalence,
                "pre_existing_medications": {
                    key: med.__dict__ for key, med in generation_config.pre_existing_medications.items()
                },
                "backend": self.backend,
                "resume": self.resume,
                "batch_size": self.batch_size,
            }
        )

        runner = self._build_runner()
        simulation = PopulationSimulation(
            self.db, use_multiprocessing=runner.backend == "local"
        )

        with self._progress("Simulating...") as progress:
            task = progress.add_task("Simulating...", total=None)

            results = simulation.run_simulation(
                protocol,
                n_patients=n_patients,
                duration_days=duration,
                generation_config=generation_config,
                runner=runner,
                checkpoint_stage="simulation",
                batch_size=self.batch_size,
            )

        # Display results
        self._display_simulation_results(results, protocol)

        tracker.log_metrics(
            "simulation",
            {
                "success_rate": results.get("success_rate"),
                "tolerance_rate": results.get("tolerance_rate"),
                "addiction_rate": results.get("addiction_rate"),
                "withdrawal_rate": results.get("withdrawal_rate"),
                "adverse_event_rate": results.get("adverse_event_rate"),
                "avg_pain_score": results.get("avg_pain_score"),
                "avg_analgesia": results.get("avg_analgesia"),
                "avg_side_effects": results.get("avg_side_effects"),
                "avg_g_activation": results.get("avg_g_activation"),
                "avg_beta_activation": results.get("avg_beta_activation"),
                "avg_quality_of_life": results.get("avg_quality_of_life"),
                "avg_baseline_tolerance": results.get("avg_baseline_tolerance"),
                "computation_time": results.get("computation_time"),
                **{k: v for k, v in results.items() if k.startswith("nt_")},
                **{k: v for k, v in results.items() if k.startswith("med_")},
            },
        )
        tracker.log_artifact(
            "simulation_results.json",
            {"protocol": protocol.to_dict(), "metrics": results},
        )

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

        binding_table = Table(title="Receptor Engagement", box=box.SIMPLE_HEAVY)
        binding_table.add_column("Metric")
        binding_table.add_column("Value", justify="right")
        binding_table.add_row("Avg G-protein activation", f"{results.get('avg_g_activation', 0)*100:6.2f}%")
        binding_table.add_row("Avg β-arrestin activation", f"{results.get('avg_beta_activation', 0)*100:6.2f}%")

        nt_table = Table(title="Neurotransmitter Release (avg units)", box=box.SIMPLE)
        nt_table.add_column("Transmitter")
        nt_table.add_column("Level", justify="right")
        for key in [k for k in results.keys() if k.startswith('nt_')]:
            label = key.replace('nt_', '').replace('_', ' ').title()
            nt_table.add_row(label, f"{results[key]:6.2f}")

        self.console.print("\n")
        med_keys = [k for k in results.keys() if k.startswith('med_')]
        tables = [binding_table, nt_table]
        if med_keys:
            med_table = Table(title="Pre-existing Medication Exposure", box=box.SIMPLE)
            med_table.add_column("Medication")
            med_table.add_column("Rate", justify="right")
            for key in med_keys:
                label = key.replace('med_', '').replace('_', ' ').title()
                med_table.add_row(label, f"{results[key]*100:6.2f}%")
            tables.append(med_table)

        self.console.print(Columns(tables))

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
        clinical.add_row(
            "Baseline Tolerance",
            f"{results.get('avg_baseline_tolerance', 0):.3f}",
            "",
        )

        self.console.print("\n")
        self.console.print(clinical)

        self.console.print(f"\n[dim]Computation time: {results['computation_time']:.2f}s[/dim]")

        Prompt.ask("\nPress Enter to continue")

    def run_history_menu(self):
        """Display run metadata and metrics from ExperimentTracker outputs."""
        self.console.clear()
        self.console.print("\n[bold cyan]═══ Run Dashboard ═══[/bold cyan]\n")

        runs_root = Path(self.checkpoint_dir)
        if not runs_root.exists():
            self.console.print("[yellow]No runs recorded yet.[/yellow]")
            Prompt.ask("\nPress Enter to continue")
            return

        runs = sorted([p for p in runs_root.iterdir() if p.is_dir()])
        if not runs:
            self.console.print("[yellow]No runs recorded yet.[/yellow]")
            Prompt.ask("\nPress Enter to continue")
            return

        options = {str(i + 1): run for i, run in enumerate(runs)}
        run_table = Table(title="Tracked Runs", box=box.ROUNDED)
        run_table.add_column("#", justify="right")
        run_table.add_column("Run ID", style="cyan")
        run_table.add_column("Created", style="green")
        run_table.add_column("Backend", style="magenta")

        for idx, run_path in options.items():
            meta_path = run_path / "metadata.json"
            backend = "?"
            created = "?"
            if meta_path.exists():
                with meta_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                backend = meta.get("backend", meta.get("platform", "?"))
                created = meta.get("created_utc", "?")
            run_table.add_row(idx, run_path.name, created, backend)

        self.console.print(run_table)
        selection = Prompt.ask("Select run to inspect (or Enter to exit)", default="")
        if selection not in options:
            return

        run_path = options[selection]
        self._render_run_summary(run_path)
        Prompt.ask("\nPress Enter to continue")

    def _render_run_summary(self, run_path: Path):
        meta_path = run_path / "metadata.json"
        metrics_path = run_path / "metrics.jsonl"

        meta = {}
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as f:
                meta = json.load(f)

        sig_ok, sig_msg = ExperimentTracker.verify_signature_for_run(run_path)
        sig_style = "green" if sig_ok else "red"
        self.console.print(f"[{sig_style}]{sig_msg}[/{sig_style}]")

        header = Table(box=box.ROUNDED)
        header.add_column("Field", style="cyan")
        header.add_column("Value")
        header.add_row("Run ID", meta.get("run_id", run_path.name))
        header.add_row("Created", meta.get("created_utc", "?"))
        header.add_row("Backend", meta.get("backend", meta.get("platform", "?")))
        header.add_row("Python", meta.get("python", "?"))
        header.add_row("Host", meta.get("hostname", "?"))
        self.console.print(header)

        if metrics_path.exists():
            metrics_table = Table(title="Metrics", box=box.ROUNDED)
            metrics_table.add_column("Stage", style="green")
            metrics_table.add_column("Timestamp", style="cyan")
            metrics_table.add_column("Payload", style="magenta")

            with metrics_path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        payload = json.loads(line)
                        metrics_table.add_row(
                            payload.get("stage", "?"),
                            payload.get("timestamp", "?"),
                            json.dumps(payload.get("metrics", {})),
                        )
                    except json.JSONDecodeError:
                        continue

            self.console.print(metrics_table)
        else:
            self.console.print("[yellow]No metrics recorded.[/yellow]")

        tracker = ExperimentTracker(
            base_dir=self.checkpoint_dir, run_id=run_path.name, write_signature=False
        )
        audit_events = tracker.read_audit_events()[-5:]
        if audit_events:
            audit_table = Table(title="Recent Audit Trail", box=box.ROUNDED)
            audit_table.add_column("When", style="cyan")
            audit_table.add_column("User", style="magenta")
            audit_table.add_column("Action", style="green")
            for event in audit_events:
                audit_table.add_row(
                    event.get("timestamp", "?"),
                    event.get("user", "?"),
                    event.get("action", "?"),
                )
            self.console.print(audit_table)

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

        backend_choice = Prompt.ask(
            "Execution backend (local/ray/dask)",
            choices=["local", "ray", "dask"],
            default=self.backend,
        )
        self.backend = backend_choice

        self.resume = Confirm.ask("Resume from checkpoints?", default=self.resume)
        self.batch_size = IntPrompt.ask(
            "Batch size for distributed shards", default=self.batch_size
        )

        self.animations_enabled = Confirm.ask(
            "Enable smooth animations (TEMPEST Class C)",
            default=self.animations_enabled,
        )
        default_refresh = 8 if self.animations_enabled else 2
        self.refresh_hz = IntPrompt.ask(
            "Refresh rate (Hz) for progress/polling", default=self.refresh_hz or default_refresh
        )

        new_run = Prompt.ask(
            "Run ID (Enter to keep current)", default=self.current_run_id or ""
        )
        if new_run:
            self.current_run_id = new_run
            self.tracker = None  # force recreation with new run id

        new_dir = Prompt.ask(
            "Checkpoint directory", default=self.checkpoint_dir
        )
        if new_dir:
            self.checkpoint_dir = new_dir
            self.tracker = None

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
