#!/usr/bin/env python3
"""
ZeroPain Patient Simulation Framework
Large-scale patient population simulation with realistic variability
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import multiprocessing as mp
from functools import partial
import json
import time

from opioid_analysis_tools import CompoundDatabase, CompoundProfile
from opioid_optimization_framework import ProtocolConfig, PharmacokineticModel


@dataclass
class AgeDistribution:
    """Configurable age distribution using a beta prior."""

    alpha: float = 2.0
    beta: float = 3.0
    min_age: int = 18
    max_age: int = 85

    def sample(self, rng: np.random.Generator) -> int:
        age = rng.beta(self.alpha, self.beta) * (self.max_age - self.min_age)
        return int(self.min_age + age)


@dataclass
class WeightDistribution:
    """Sex-specific weight distributions."""

    male_mean: float = 82.0
    male_std: float = 15.0
    female_mean: float = 70.0
    female_std: float = 13.0
    min_weight: float = 45.0
    max_weight: float = 120.0

    def sample(self, rng: np.random.Generator, sex: str) -> float:
        if sex == 'M':
            weight = rng.normal(self.male_mean, self.male_std)
        else:
            weight = rng.normal(self.female_mean, self.female_std)
        return float(np.clip(weight, self.min_weight, self.max_weight))


@dataclass
class MedicationProfile:
    """Pre-existing medication exposure parameters."""

    name: str
    prevalence: float
    metabolism_multiplier: float = 1.0
    sensitivity_multiplier: float = 1.0
    analgesia_bonus: float = 0.0
    side_effect_bias: float = 0.0
    baseline_tolerance: float = 0.0


@dataclass
class PatientGenerationConfig:
    """User-adjustable virtual population controls."""

    population_size: Optional[int] = None
    sex_ratio_male: float = 0.5
    age_distribution: AgeDistribution = field(default_factory=AgeDistribution)
    weight_distribution: WeightDistribution = field(default_factory=WeightDistribution)
    comorbidity_prevalence: Dict[str, float] = field(
        default_factory=lambda: {
            'hypertension': 0.18,
            'diabetes': 0.12,
            'depression': 0.11,
            'anxiety': 0.14,
            'arthritis': 0.16,
            'COPD': 0.08,
            'kidney_disease': 0.07,
            'liver_disease': 0.06,
        }
    )
    pain_alpha: float = 3.0
    pain_beta: float = 2.0
    sensitivity_mean: float = 0.0
    sensitivity_sigma: float = 0.3
    metabolism_sigma: float = 0.25
    pre_existing_medications: Dict[str, MedicationProfile] = field(
        default_factory=lambda: {
            "ssri_snri": MedicationProfile(
                name="SSRI/SNRI",
                prevalence=0.18,
                sensitivity_multiplier=1.05,
                side_effect_bias=0.05,
            ),
            "benzodiazepine": MedicationProfile(
                name="Benzodiazepine",
                prevalence=0.08,
                sensitivity_multiplier=0.95,
                side_effect_bias=0.08,
                baseline_tolerance=0.05,
            ),
            "gabapentinoid": MedicationProfile(
                name="Gabapentinoid",
                prevalence=0.15,
                analgesia_bonus=0.06,
                sensitivity_multiplier=1.02,
            ),
            "nsaid": MedicationProfile(
                name="NSAID",
                prevalence=0.25,
                analgesia_bonus=0.04,
            ),
            "stimulant": MedicationProfile(
                name="Stimulant",
                prevalence=0.06,
                metabolism_multiplier=1.08,
                side_effect_bias=0.03,
            ),
            "cannabis": MedicationProfile(
                name="Cannabis",
                prevalence=0.10,
                sensitivity_multiplier=0.98,
                analgesia_bonus=0.02,
                baseline_tolerance=0.02,
            ),
        }
    )


@dataclass
class PatientProfile:
    """Individual patient characteristics"""
    patient_id: int
    age: int
    weight: float  # kg
    sex: str  # 'M' or 'F'
    metabolism_rate: float  # Multiplier for drug clearance
    sensitivity: float  # Receptor sensitivity multiplier
    pain_severity: float  # 0-10 baseline pain
    comorbidities: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    baseline_tolerance: float = 0.0
    medication_effects: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'patient_id': self.patient_id,
            'age': self.age,
            'weight': self.weight,
            'sex': self.sex,
            'metabolism_rate': self.metabolism_rate,
            'sensitivity': self.sensitivity,
            'pain_severity': self.pain_severity,
            'comorbidities': self.comorbidities,
            'medications': self.medications,
            'baseline_tolerance': self.baseline_tolerance,
            'medication_effects': self.medication_effects,
        }


@dataclass
class SimulationResult:
    """Results from patient simulation"""
    patient: PatientProfile
    success: bool
    tolerance_developed: bool
    addiction_signs: bool
    withdrawal_symptoms: bool
    adverse_events: List[str]
    avg_pain_score: float
    avg_analgesia: float
    avg_side_effects: float
    quality_of_life: float
    avg_g_activation: float
    avg_beta_activation: float
    neurotransmitter_release: Dict[str, float]

    def to_dict(self) -> Dict:
        return {
            'patient': self.patient.to_dict(),
            'success': self.success,
            'tolerance_developed': self.tolerance_developed,
            'addiction_signs': self.addiction_signs,
            'withdrawal_symptoms': self.withdrawal_symptoms,
            'adverse_events': self.adverse_events,
            'avg_pain_score': self.avg_pain_score,
            'avg_analgesia': self.avg_analgesia,
            'avg_side_effects': self.avg_side_effects,
            'quality_of_life': self.quality_of_life,
            'avg_g_activation': self.avg_g_activation,
            'avg_beta_activation': self.avg_beta_activation,
            'neurotransmitter_release': self.neurotransmitter_release,
        }

    @classmethod
    def from_dict(cls, payload: Dict) -> "SimulationResult":
        return cls(
            patient=PatientProfile(**payload['patient']),
            success=payload['success'],
            tolerance_developed=payload['tolerance_developed'],
            addiction_signs=payload['addiction_signs'],
            withdrawal_symptoms=payload['withdrawal_symptoms'],
            adverse_events=payload['adverse_events'],
            avg_pain_score=payload['avg_pain_score'],
            avg_analgesia=payload['avg_analgesia'],
            avg_side_effects=payload['avg_side_effects'],
            quality_of_life=payload['quality_of_life'],
            avg_g_activation=payload.get('avg_g_activation', 0.0),
            avg_beta_activation=payload.get('avg_beta_activation', 0.0),
            neurotransmitter_release=payload.get('neurotransmitter_release', {}),
        )


class PatientGenerator:
    """Generate realistic virtual patient populations"""

    @staticmethod
    def generate_patient(
        patient_id: int,
        seed: Optional[int] = None,
        config: Optional[PatientGenerationConfig] = None,
    ) -> PatientProfile:
        """Generate a single virtual patient with realistic characteristics"""
        cfg = config or PatientGenerationConfig()
        rng = np.random.default_rng(seed + patient_id if seed is not None else None)

        # Age distribution (configurable beta)
        age = cfg.age_distribution.sample(rng)

        # Weight distribution (45-120 kg by default, configurable)
        sex = 'M' if rng.random() < cfg.sex_ratio_male else 'F'
        weight = cfg.weight_distribution.sample(rng, sex)

        # Metabolism rate (log-normal distribution)
        base_metabolism = float(rng.lognormal(0, cfg.metabolism_sigma))

        # Age effect on metabolism
        if age > 65:
            base_metabolism *= 0.8
        elif age < 25:
            base_metabolism *= 1.2

        # Receptor sensitivity (log-normal distribution)
        sensitivity = float(
            rng.lognormal(cfg.sensitivity_mean, cfg.sensitivity_sigma)
        )

        # Pain severity (beta distribution)
        pain_severity = float(rng.beta(cfg.pain_alpha, cfg.pain_beta) * 10)

        # Pre-existing medications (affect metabolism, sensitivity, tolerance)
        medications: List[str] = []
        medication_effects = {
            'metabolism_multiplier': 1.0,
            'sensitivity_multiplier': 1.0,
            'analgesia_bonus': 0.0,
            'side_effect_bias': 0.0,
            'baseline_tolerance': 0.0,
        }
        for med_profile in cfg.pre_existing_medications.values():
            if rng.random() < med_profile.prevalence:
                medications.append(med_profile.name)
                medication_effects['metabolism_multiplier'] *= med_profile.metabolism_multiplier
                medication_effects['sensitivity_multiplier'] *= med_profile.sensitivity_multiplier
                medication_effects['analgesia_bonus'] += med_profile.analgesia_bonus
                medication_effects['side_effect_bias'] += med_profile.side_effect_bias
                medication_effects['baseline_tolerance'] += med_profile.baseline_tolerance

        base_metabolism *= medication_effects['metabolism_multiplier']
        sensitivity *= medication_effects['sensitivity_multiplier']

        # Comorbidities (driven by configurable prevalence)
        comorbidities = []
        possible_comorbidities = list(cfg.comorbidity_prevalence.keys())
        for condition in possible_comorbidities:
            prevalence = cfg.comorbidity_prevalence.get(condition, 0.0)
            # Age sensitivity: increase prevalence in older cohorts
            age_factor = 1.0 + max(0, (age - 50)) * 0.01
            if rng.random() < min(1.0, prevalence * age_factor):
                comorbidities.append(condition)

        # Liver disease reduces metabolism
        if 'liver_disease' in comorbidities:
            base_metabolism *= 0.6

        # Kidney disease affects clearance
        if 'kidney_disease' in comorbidities:
            base_metabolism *= 0.7

        return PatientProfile(
            patient_id=patient_id,
            age=age,
            weight=weight,
            sex=sex,
            metabolism_rate=base_metabolism,
            sensitivity=sensitivity,
            pain_severity=pain_severity,
            comorbidities=comorbidities,
            medications=medications,
            baseline_tolerance=medication_effects['baseline_tolerance'],
            medication_effects=medication_effects,
        )

    @classmethod
    def generate_population(
        cls,
        n_patients: int,
        seed: Optional[int] = 42,
        config: Optional[PatientGenerationConfig] = None,
    ) -> List[PatientProfile]:
        """Generate population of virtual patients"""
        cfg = config or PatientGenerationConfig()
        total = cfg.population_size or n_patients
        return [cls.generate_patient(i, seed, cfg) for i in range(total)]


class PatientSimulator:
    """Simulate patient response to opioid protocols"""

    def __init__(self, compound_database: CompoundDatabase):
        self.db = compound_database
        self.pk_model = PharmacokineticModel()

    def simulate_patient(self, patient: PatientProfile,
                        protocol: ProtocolConfig,
                        duration_days: int = 90) -> SimulationResult:
        """
        Simulate patient response to protocol over time

        Args:
            patient: Patient profile
            protocol: Treatment protocol
            duration_days: Simulation duration in days

        Returns:
            SimulationResult with outcomes
        """
        # Get compound profiles
        compounds = [self.db.get_compound(name) for name in protocol.compounds]
        compounds = [c for c in compounds if c is not None]

        if not compounds:
            raise ValueError("No valid compounds in protocol")

        # Simulation parameters
        hours_per_day = 24
        time_step = 0.25  # 15-minute intervals
        n_timepoints = int(duration_days * hours_per_day / time_step)

        # Initialize tracking arrays
        pain_scores = np.zeros(n_timepoints)
        analgesia_levels = np.zeros(n_timepoints)
        side_effect_levels = np.zeros(n_timepoints)
        g_activation_levels = np.zeros(n_timepoints)
        beta_activation_levels = np.zeros(n_timepoints)
        neurotransmitter_totals = {
            'endorphins': 0.0,
            'dopamine': 0.0,
            'serotonin': 0.0,
            'norepinephrine': 0.0,
            'substance_p': 0.0,
        }
        tolerance_level = max(0.0, patient.baseline_tolerance)
        tolerance_history = []
        med_effects = patient.medication_effects or {}

        # Adverse events tracking
        adverse_events = []

        # Volume of distribution adjusted for weight
        volume_dist = patient.weight * 0.7  # L/kg

        # Simulate each timepoint
        for t_idx in range(n_timepoints):
            t_hours = t_idx * time_step
            t_days = t_hours / hours_per_day

            # Calculate time of day for dosing
            time_of_day = t_hours % hours_per_day

            total_analgesia = 0.0
            total_side_effects = 0.0
            g_sum = 0.0
            beta_sum = 0.0

            # Calculate contribution from each compound
            for compound, dose, freq in zip(compounds, protocol.doses, protocol.frequencies):
                # Determine if dose should be administered
                interval = hours_per_day / freq
                dose_times = [i * interval for i in range(int(freq))]

                # Find time since last dose
                time_since_dose = min([time_of_day - dt if time_of_day >= dt
                                      else time_of_day + hours_per_day - dt
                                      for dt in dose_times])

                # Calculate concentration
                adjusted_t_half = compound.t_half / patient.metabolism_rate

                concentration = self.pk_model.calculate_concentration(
                    dose, time_since_dose, adjusted_t_half,
                    compound.bioavailability, volume_dist
                )

                # Determine binding site
                if compound.ki_orthosteric != float('inf'):
                    ki = compound.ki_orthosteric
                elif compound.ki_allosteric1 != float('inf'):
                    ki = compound.ki_allosteric1
                else:
                    ki = 50.0  # Default

                # Calculate receptor occupancy with patient sensitivity
                g_activation = self.pk_model.calculate_receptor_occupancy(
                    concentration * patient.sensitivity,
                    ki,
                    compound.intrinsic_activity * compound.g_protein_bias
                )

                beta_activation = self.pk_model.calculate_receptor_occupancy(
                    concentration * patient.sensitivity,
                    ki,
                    compound.intrinsic_activity * compound.beta_arrestin_bias
                )

                neurotransmitters = self.pk_model.calculate_neurotransmitter_release(
                    g_activation, beta_activation
                )
                for name, value in neurotransmitters.items():
                    neurotransmitter_totals[name] += value

                # Update tolerance
                if not compound.reverses_tolerance:
                    tolerance_increment = compound.tolerance_rate * beta_activation * 0.0001
                    tolerance_level += tolerance_increment

                # Apply tolerance reversal effects
                if compound.reverses_tolerance and tolerance_level > 0:
                    tolerance_level *= 0.9995  # Gradual reversal

                # Calculate effective tolerance
                if compound.reverses_tolerance:
                    effective_tolerance = max(0, tolerance_level * 0.3)
                elif compound.prevents_withdrawal:
                    effective_tolerance = tolerance_level * 0.5
                else:
                    effective_tolerance = tolerance_level

                effective_tolerance = min(effective_tolerance, 0.95)

                # Calculate analgesia
                analgesia = self.pk_model.calculate_analgesia(
                    g_activation, effective_tolerance
                )

                total_analgesia += analgesia
                total_side_effects += beta_activation
                g_sum += g_activation
                beta_sum += beta_activation

            # Medication modulation
            total_analgesia += med_effects.get('analgesia_bonus', 0.0)
            total_side_effects += med_effects.get('side_effect_bias', 0.0)

            # Cap maximum effects
            total_analgesia = min(total_analgesia, 1.0)
            total_side_effects = min(total_side_effects, 1.0)

            g_activation_levels[t_idx] = g_sum / max(len(compounds), 1)
            beta_activation_levels[t_idx] = beta_sum / max(len(compounds), 1)

            # Calculate pain score (0-10 scale)
            baseline_pain = patient.pain_severity
            pain_relief = total_analgesia * baseline_pain
            current_pain = max(0, baseline_pain - pain_relief)

            # Check for adverse events
            if total_side_effects > 0.7:
                if np.random.random() < 0.001:  # Low probability per timepoint
                    adverse_events.append(f"High side effects at day {t_days:.1f}")

            # Store results
            pain_scores[t_idx] = current_pain
            analgesia_levels[t_idx] = total_analgesia
            side_effect_levels[t_idx] = total_side_effects
            tolerance_history.append(tolerance_level)

        # Calculate outcomes
        avg_pain_score = np.mean(pain_scores)
        avg_analgesia = np.mean(analgesia_levels)
        avg_side_effects = np.mean(side_effect_levels)
        avg_g_activation = np.mean(g_activation_levels)
        avg_beta_activation = np.mean(beta_activation_levels)
        avg_neurotransmitters = {
            k: v / n_timepoints for k, v in neurotransmitter_totals.items()
        }
        final_tolerance = tolerance_level

        # Success criteria
        success = (
            avg_pain_score < 4.0 and  # Adequate pain control
            avg_analgesia > 0.5 and
            avg_side_effects < 0.4 and
            final_tolerance < 0.5
        )

        # Tolerance development
        tolerance_developed = final_tolerance > 0.5

        # Addiction risk factors
        addiction_risk = avg_side_effects * 0.25
        if 'depression' in patient.comorbidities:
            addiction_risk *= 1.5
        if 'anxiety' in patient.comorbidities:
            addiction_risk *= 1.3

        addiction_signs = np.random.random() < addiction_risk

        # Withdrawal assessment
        has_withdrawal_protection = any(
            self.db.get_compound(name).prevents_withdrawal
            for name in protocol.compounds
            if self.db.get_compound(name)
        )

        if has_withdrawal_protection:
            withdrawal_risk = 0.02
        else:
            withdrawal_risk = 0.15 + final_tolerance * 0.1

        withdrawal_symptoms = np.random.random() < withdrawal_risk

        # Quality of life score (0-1)
        pain_impact = (10 - avg_pain_score) / 10
        side_effect_impact = 1 - avg_side_effects
        quality_of_life = (pain_impact * 0.6 + side_effect_impact * 0.4)

        # Additional adverse events
        if avg_side_effects > 0.6:
            adverse_events.append("Persistent side effects")
        if final_tolerance > 0.7:
            adverse_events.append("Significant tolerance development")

        return SimulationResult(
            patient=patient,
            success=success,
            tolerance_developed=tolerance_developed,
            addiction_signs=addiction_signs,
            withdrawal_symptoms=withdrawal_symptoms,
            adverse_events=adverse_events,
            avg_pain_score=avg_pain_score,
            avg_analgesia=avg_analgesia,
            avg_side_effects=avg_side_effects,
            quality_of_life=quality_of_life,
            avg_g_activation=avg_g_activation,
            avg_beta_activation=avg_beta_activation,
            neurotransmitter_release=avg_neurotransmitters,
        )


class PopulationSimulation:
    """Large-scale population simulation"""

    def __init__(self, compound_database: CompoundDatabase,
                 use_multiprocessing: bool = True):
        self.db = compound_database
        self.simulator = PatientSimulator(compound_database)
        self.use_multiprocessing = use_multiprocessing
        self.n_cores = mp.cpu_count()
        self.accelerator_hint = self._detect_intel_accelerator()

    def run_simulation(self, protocol: ProtocolConfig,
                      n_patients: int = 100000,
                      duration_days: int = 90,
                      seed: int = 42,
                      generation_config: Optional[PatientGenerationConfig] = None,
                      runner=None,
                      checkpoint_stage: str = 'simulation',
                      batch_size: int = 256) -> Dict:
        """
        Run large-scale population simulation

        Args:
            protocol: Treatment protocol
            n_patients: Number of virtual patients
            duration_days: Simulation duration
            seed: Random seed

        Returns:
            Dictionary with aggregated results
        """
        print(f"\nGenerating {n_patients:,} virtual patients...")
        start_time = time.time()

        # Generate patient population
        generator = PatientGenerator()
        patients = generator.generate_population(
            n_patients, seed, generation_config
        )

        gen_time = time.time() - start_time
        print(f"  Generated in {gen_time:.2f} seconds")

        print(f"\nSimulating {duration_days}-day protocol...")
        print(f"  Compounds: {', '.join(protocol.compounds)}")
        print(f"  Using {self.n_cores} CPU cores")
        if self.accelerator_hint:
            print(f"  Accelerator hint: OpenVINO {self.accelerator_hint} (NPU/Arc preferred)")

        sim_start = time.time()

        # Run simulations
        if runner is not None:
            simulate_func = partial(
                self.simulator.simulate_patient,
                protocol=protocol,
                duration_days=duration_days
            )
            results = runner.map(
                simulate_func,
                patients,
                stage_name=checkpoint_stage,
                batch_size=batch_size,
                dump_fn=lambda batch: [r.to_dict() for r in batch],
                load_fn=lambda payload: [SimulationResult.from_dict(item) for item in payload],
            )
        elif self.use_multiprocessing and n_patients > 100:
            # Parallel simulation
            n_workers = min(self.n_cores - 1, 16)
            print(f"  Parallel processing with {n_workers} workers")

            with mp.Pool(n_workers) as pool:
                simulate_func = partial(
                    self._simulate_wrapper,
                    protocol=protocol,
                    duration_days=duration_days
                )
                results = pool.map(simulate_func, patients)
        else:
            # Serial simulation
            print(f"  Serial processing")
            results = [
                self.simulator.simulate_patient(patient, protocol, duration_days)
                for patient in patients
            ]

        sim_time = time.time() - sim_start
        print(f"  Simulated in {sim_time:.2f} seconds")
        print(f"  Rate: {n_patients/sim_time:.0f} patients/second")

        # Aggregate results
        print("\nAggregating results...")
        aggregated = self._aggregate_results(results)

        total_time = time.time() - start_time
        aggregated['computation_time'] = total_time
        aggregated['n_patients'] = n_patients

        return aggregated

    @staticmethod
    def _detect_intel_accelerator() -> Optional[str]:
        try:
            from openvino.runtime import Core

            devices = Core().available_devices
            if 'NPU' in devices:
                return 'NPU'
            if 'GPU' in devices:
                return 'GPU'
            if devices:
                return devices[0]
        except Exception:
            return None
        return None

    def _simulate_wrapper(self, patient: PatientProfile,
                         protocol: ProtocolConfig,
                         duration_days: int) -> SimulationResult:
        """Wrapper for multiprocessing"""
        return self.simulator.simulate_patient(patient, protocol, duration_days)

    def _aggregate_results(self, results: List[SimulationResult]) -> Dict:
        """Aggregate simulation results"""
        n_patients = len(results)

        # Count outcomes
        success_count = sum(1 for r in results if r.success)
        tolerance_count = sum(1 for r in results if r.tolerance_developed)
        addiction_count = sum(1 for r in results if r.addiction_signs)
        withdrawal_count = sum(1 for r in results if r.withdrawal_symptoms)
        adverse_count = sum(1 for r in results if len(r.adverse_events) > 0)

        # Calculate metrics
        metrics = {
            'success_rate': success_count / n_patients,
            'tolerance_rate': tolerance_count / n_patients,
            'addiction_rate': addiction_count / n_patients,
            'withdrawal_rate': withdrawal_count / n_patients,
            'adverse_event_rate': adverse_count / n_patients,
            'avg_pain_score': np.mean([r.avg_pain_score for r in results]),
            'avg_analgesia': np.mean([r.avg_analgesia for r in results]),
            'avg_side_effects': np.mean([r.avg_side_effects for r in results]),
            'avg_quality_of_life': np.mean([r.quality_of_life for r in results]),
            'avg_g_activation': np.mean([r.avg_g_activation for r in results]),
            'avg_beta_activation': np.mean([
                r.avg_beta_activation for r in results
            ]),
            'avg_baseline_tolerance': np.mean([
                r.patient.baseline_tolerance for r in results
            ]),
        }

        # Medication exposures
        medication_counts: Dict[str, int] = {}
        for r in results:
            for med in r.patient.medications:
                medication_counts[med] = medication_counts.get(med, 0) + 1
        for med, count in medication_counts.items():
            metrics[f"med_{med.lower().replace(' ', '_')}_rate"] = count / n_patients

        # Neurotransmitter summary (mean across patients)
        if results and results[0].neurotransmitter_release:
            for nt in results[0].neurotransmitter_release.keys():
                metrics[f'nt_{nt}'] = np.mean(
                    [r.neurotransmitter_release.get(nt, 0.0) for r in results]
                )

        # Distribution statistics
        metrics['pain_score_std'] = np.std([r.avg_pain_score for r in results])
        metrics['analgesia_std'] = np.std([r.avg_analgesia for r in results])
        metrics['qol_std'] = np.std([r.quality_of_life for r in results])

        return metrics


def run_100k_simulation(protocol: ProtocolConfig) -> Dict:
    """Convenience function to run 100k patient simulation"""
    db = CompoundDatabase()
    simulation = PopulationSimulation(db, use_multiprocessing=True)

    results = simulation.run_simulation(
        protocol,
        n_patients=100000,
        duration_days=90
    )

    return results


if __name__ == '__main__':
    print("ZeroPain Patient Simulation Framework")
    print("=" * 60)

    # Example protocol
    protocol = ProtocolConfig(
        compounds=['SR-17018', 'SR-14968', 'Oxycodone'],
        doses=[16.17, 25.31, 5.07],
        frequencies=[2, 1, 4]
    )

    # Run simulation (smaller for demo)
    db = CompoundDatabase()
    simulation = PopulationSimulation(db, use_multiprocessing=True)

    results = simulation.run_simulation(
        protocol,
        n_patients=10000,  # Reduced for demo
        duration_days=90
    )

    print("\n" + "=" * 60)
    print("SIMULATION RESULTS")
    print("=" * 60)

    print(f"\nPrimary Outcomes (n={results['n_patients']:,}):")
    print(f"  Treatment Success:     {results['success_rate']*100:6.2f}%")
    print(f"  Tolerance Development: {results['tolerance_rate']*100:6.2f}%")
    print(f"  Addiction Signs:       {results['addiction_rate']*100:6.2f}%")
    print(f"  Withdrawal Symptoms:   {results['withdrawal_rate']*100:6.2f}%")
    print(f"  Adverse Events:        {results['adverse_event_rate']*100:6.2f}%")

    print(f"\nClinical Metrics:")
    print(f"  Average Pain Score:    {results['avg_pain_score']:6.2f} / 10")
    print(f"  Average Analgesia:     {results['avg_analgesia']*100:6.2f}%")
    print(f"  Average Side Effects:  {results['avg_side_effects']*100:6.2f}%")
    print(f"  Quality of Life:       {results['avg_quality_of_life']*100:6.2f}%")

    print(f"\nComputation Time:        {results['computation_time']:.2f} seconds")
