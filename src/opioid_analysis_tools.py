#!/usr/bin/env python3
"""
ZeroPain Opioid Analysis Tools
Comprehensive compound database and analysis framework with custom compound integration
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import json
import os

@dataclass
class CompoundProfile:
    """Complete pharmacological profile of an opioid compound"""
    name: str
    ki_orthosteric: float  # nM - orthosteric binding affinity
    ki_allosteric1: float  # nM - primary allosteric site
    ki_allosteric2: float  # nM - secondary allosteric site
    g_protein_bias: float  # G-protein pathway bias
    beta_arrestin_bias: float  # β-arrestin pathway bias
    t_half: float  # hours - elimination half-life
    bioavailability: float  # 0-1 - oral bioavailability
    intrinsic_activity: float  # 0-1 - receptor activation efficacy
    tolerance_rate: float  # 0-1 - rate of tolerance development
    prevents_withdrawal: bool = False
    reverses_tolerance: bool = False
    receptor_type: str = "MOR"  # MOR, DOR, KOR
    pharmacological_activities: List[str] = field(default_factory=list)
    mechanism_notes: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'ki_orthosteric': self.ki_orthosteric,
            'ki_allosteric1': self.ki_allosteric1,
            'ki_allosteric2': self.ki_allosteric2,
            'g_protein_bias': self.g_protein_bias,
            'beta_arrestin_bias': self.beta_arrestin_bias,
            't_half': self.t_half,
            'bioavailability': self.bioavailability,
            'intrinsic_activity': self.intrinsic_activity,
            'tolerance_rate': self.tolerance_rate,
            'prevents_withdrawal': self.prevents_withdrawal,
            'reverses_tolerance': self.reverses_tolerance,
            'receptor_type': self.receptor_type,
            'pharmacological_activities': self.pharmacological_activities,
            'mechanism_notes': self.mechanism_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CompoundProfile':
        """Create from dictionary"""
        return cls(**data)

    def calculate_safety_score(self) -> float:
        """Calculate comprehensive safety score (0-100)"""
        score = 100.0

        # Penalize high intrinsic activity without bias
        if self.intrinsic_activity > 0.7 and self.g_protein_bias < 5:
            score -= 20

        # Penalize high β-arrestin
        if self.beta_arrestin_bias > 0.5:
            score -= 30

        # Reward high G-protein bias
        if self.g_protein_bias > 10:
            score += 10
        elif self.g_protein_bias > 5:
            score += 5

        # Reward tolerance prevention
        if self.tolerance_rate < 0.2:
            score += 10
        if self.reverses_tolerance:
            score += 20
        if self.prevents_withdrawal:
            score += 10

        # Penalize poor pharmacokinetics
        if self.bioavailability < 0.3:
            score -= 10
        if self.t_half < 2:
            score -= 10

        return max(0.0, min(100.0, score))

    def get_bias_ratio(self) -> float:
        """Calculate G-protein/beta-arrestin bias ratio"""
        if self.beta_arrestin_bias == 0:
            return float('inf')
        return self.g_protein_bias / self.beta_arrestin_bias


class CompoundDatabase:
    """Comprehensive database of opioid compounds"""

    def __init__(self):
        self.compounds = self._initialize_compounds()
        self.custom_compounds = {}
        self.external_sources = self._source_list()

    def _initialize_compounds(self) -> Dict[str, CompoundProfile]:
        """Initialize database with known compounds"""
        compounds = {
            # FDA-approved compounds
            'Morphine': CompoundProfile(
                name='Morphine',
                ki_orthosteric=1.8,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=1.0,
                beta_arrestin_bias=1.0,
                t_half=3.0,
                bioavailability=0.3,
                intrinsic_activity=1.0,
                tolerance_rate=0.8
            ),
            'Oxycodone': CompoundProfile(
                name='Oxycodone',
                ki_orthosteric=18.0,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=1.0,
                beta_arrestin_bias=1.0,
                t_half=3.5,
                bioavailability=0.87,
                intrinsic_activity=0.9,
                tolerance_rate=0.7
            ),
            'Fentanyl': CompoundProfile(
                name='Fentanyl',
                ki_orthosteric=0.39,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=1.0,
                beta_arrestin_bias=1.2,
                t_half=3.7,
                bioavailability=0.5,
                intrinsic_activity=1.0,
                tolerance_rate=0.9
            ),
            'Buprenorphine': CompoundProfile(
                name='Buprenorphine',
                ki_orthosteric=0.2,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=1.5,
                beta_arrestin_bias=0.8,
                t_half=37.0,
                bioavailability=0.15,
                intrinsic_activity=0.3,
                tolerance_rate=0.1,
                prevents_withdrawal=True
            ),
            'Oliceridine': CompoundProfile(
                name='Oliceridine',
                ki_orthosteric=8.0,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=3.0,
                beta_arrestin_bias=1.0,
                t_half=2.0,
                bioavailability=0.3,
                intrinsic_activity=0.8,
                tolerance_rate=0.6
            ),
            'Tapentadol': CompoundProfile(
                name='Tapentadol',
                ki_orthosteric=100.0,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=1.2,
                beta_arrestin_bias=0.9,
                t_half=4.0,
                bioavailability=0.32,
                intrinsic_activity=0.88,
                tolerance_rate=0.4
            ),
            'Tramadol': CompoundProfile(
                name='Tramadol',
                ki_orthosteric=2400.0,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=1.0,
                beta_arrestin_bias=1.0,
                t_half=6.0,
                bioavailability=0.75,
                intrinsic_activity=0.1,
                tolerance_rate=0.3
            ),

            # Experimental biased agonists
            'PZM21': CompoundProfile(
                name='PZM21',
                ki_orthosteric=2.5,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=10.0,
                beta_arrestin_bias=0.1,
                t_half=3.0,
                bioavailability=0.2,
                intrinsic_activity=0.6,
                tolerance_rate=0.2
            ),
            'SR-17018': CompoundProfile(
                name='SR-17018',
                ki_orthosteric=float('inf'),
                ki_allosteric1=26.0,
                ki_allosteric2=100.0,
                g_protein_bias=8.2,
                beta_arrestin_bias=0.01,
                t_half=7.0,
                bioavailability=0.7,
                intrinsic_activity=0.38,
                tolerance_rate=0.0,
                prevents_withdrawal=True,
                reverses_tolerance=True
            ),
            'SR-14968': CompoundProfile(
                name='SR-14968',
                ki_orthosteric=float('inf'),
                ki_allosteric1=10.0,
                ki_allosteric2=50.0,
                g_protein_bias=10.0,
                beta_arrestin_bias=0.1,
                t_half=12.0,
                bioavailability=0.8,
                intrinsic_activity=0.65,
                tolerance_rate=0.15
            ),

            # Natural compounds
            'Mitragynine': CompoundProfile(
                name='Mitragynine',
                ki_orthosteric=160.0,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=2.0,
                beta_arrestin_bias=0.5,
                t_half=3.5,
                bioavailability=0.2,
                intrinsic_activity=0.13,
                tolerance_rate=0.4,
                prevents_withdrawal=True
            ),
            'Nalbuphine': CompoundProfile(
                name='Nalbuphine',
                ki_orthosteric=11.0,
                ki_allosteric1=float('inf'),
                ki_allosteric2=float('inf'),
                g_protein_bias=0.8,
                beta_arrestin_bias=0.4,
                t_half=5.0,
                bioavailability=0.16,
                intrinsic_activity=0.4,
                tolerance_rate=0.2
            ),
        }

        activity_map = {
            'Morphine': ['MOR full agonist', 'DOR weak agonist', 'KOR weak agonist'],
            'Oxycodone': ['MOR full agonist', 'Norepinephrine reuptake inhibition'],
            'Fentanyl': ['MOR full agonist'],
            'Buprenorphine': ['MOR partial agonist', 'KOR antagonist', 'ORL-1 agonist'],
            'Oliceridine': ['G-protein biased MOR agonist'],
            'Tapentadol': ['MOR agonist', 'Norepinephrine reuptake inhibition'],
            'Tramadol': ['MOR weak agonist', 'SNRI'],
            'PZM21': ['Biased MOR agonist'],
            'SR-17018': ['Biased MOR agonist', 'Tolerance reversal'],
            'SR-14968': ['Biased MOR agonist'],
            'Mitragynine': ['Partial MOR agonist', 'KOR antagonist'],
            'Nalbuphine': ['KOR agonist', 'MOR antagonist'],
        }
        for name, activities in activity_map.items():
            if name in compounds:
                compounds[name].pharmacological_activities = activities

        return compounds

    def add_custom_compound(self, compound: CompoundProfile):
        """Add a custom compound to the database"""
        self.custom_compounds[compound.name] = compound

    def get_compound(self, name: str) -> Optional[CompoundProfile]:
        """Retrieve compound by name"""
        if name in self.compounds:
            return self.compounds[name]
        return self.custom_compounds.get(name)

    def list_compounds(self, category: str = 'all') -> List[str]:
        """List available compounds"""
        if category == 'all':
            return list(self.compounds.keys()) + list(self.custom_compounds.keys())
        elif category == 'standard':
            return list(self.compounds.keys())
        elif category == 'custom':
            return list(self.custom_compounds.keys())
        return []

    def filter_by_ki_range(self, ki_min: float, ki_max: float,
                          site: str = 'orthosteric') -> List[CompoundProfile]:
        """Filter compounds by Ki value range"""
        results = []
        all_compounds = {**self.compounds, **self.custom_compounds}

        for compound in all_compounds.values():
            if site == 'orthosteric':
                ki = compound.ki_orthosteric
            elif site == 'allosteric1':
                ki = compound.ki_allosteric1
            elif site == 'allosteric2':
                ki = compound.ki_allosteric2
            else:
                continue

            if ki != float('inf') and ki_min <= ki <= ki_max:
                results.append(compound)

        return results

    def filter_by_safety(self, min_score: float = 70.0) -> List[CompoundProfile]:
        """Filter compounds by minimum safety score"""
        all_compounds = {**self.compounds, **self.custom_compounds}
        return [c for c in all_compounds.values()
                if c.calculate_safety_score() >= min_score]

    def export_to_json(self, filepath: str):
        """Export database to JSON file"""
        data = {
            'standard': {name: comp.to_dict() for name, comp in self.compounds.items()},
            'custom': {name: comp.to_dict() for name, comp in self.custom_compounds.items()}
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def import_from_json(self, filepath: str):
        """Import custom compounds from JSON file"""
        if not os.path.exists(filepath):
            return

        with open(filepath, 'r') as f:
            data = json.load(f)

        if 'custom' in data:
            for name, comp_data in data['custom'].items():
                self.custom_compounds[name] = CompoundProfile.from_dict(comp_data)

    def hydrate_from_sources(self, name: str, sources: Optional[List[str]] = None) -> Optional[CompoundProfile]:
        """Fetch compound data from configured external JSON sources."""

        endpoints = sources or self.external_sources
        if not endpoints:
            return None

        for endpoint in endpoints:
            try:
                if endpoint.startswith("http"):
                    import requests  # type: ignore

                    response = requests.get(endpoint, timeout=5)
                    response.raise_for_status()
                    data = response.json()
                else:
                    with open(endpoint, 'r', encoding='utf-8') as f:
                        data = json.load(f)
            except Exception:
                continue

            comp_data = data.get(name) or data.get('compounds', {}).get(name)
            if comp_data:
                return CompoundProfile.from_dict(comp_data)

        return None

    def _source_list(self) -> List[str]:
        raw = os.environ.get("ZP_COMPOUND_SOURCES", "")
        return [entry.strip() for entry in raw.split(',') if entry.strip()]


class PharmacokineticModel:
    """PK/PD modeling for opioid compounds"""

    @staticmethod
    def calculate_concentration(
        dose: float, time: float, t_half: float, bioavailability: float,
        volume_dist: float = 50.0
    ) -> float:
        """Calculate plasma concentration at given time."""
        k_e = 0.693 / t_half  # Elimination rate constant
        c_0 = (dose * bioavailability * 1000) / volume_dist  # Initial concentration
        return c_0 * np.exp(-k_e * time)

    @staticmethod
    def calculate_receptor_occupancy(
        concentration: float, ki: float, intrinsic_activity: float
    ) -> float:
        """Calculate receptor occupancy and activation."""
        if ki == float('inf'):
            return 0.0

        occupancy = concentration / (concentration + ki)
        return occupancy * intrinsic_activity

    @staticmethod
    def calculate_analgesia(g_activation: float, tolerance: float = 0.0) -> float:
        """Calculate analgesic effect."""
        return g_activation * (1 - tolerance)

    @staticmethod
    def calculate_side_effects(beta_activation: float) -> Dict[str, float]:
        """Calculate side effect probabilities."""
        return {
            'respiratory_depression': beta_activation * 0.3,
            'constipation': beta_activation * 0.6,
            'nausea': beta_activation * 0.4,
            'sedation': beta_activation * 0.5,
        }

    @staticmethod
    def calculate_neurotransmitter_release(
        g_activation: float, beta_activation: float
    ) -> Dict[str, float]:
        """Estimate neurotransmitter release downstream of receptor activation."""
        g_act = max(0.0, min(1.0, g_activation))
        beta_act = max(0.0, min(1.0, beta_activation))

        endorphins = g_act * 120.0
        dopamine = (g_act * 60.0) + (beta_act * 15.0)
        serotonin = (g_act * 25.0) + (beta_act * 35.0)
        norepinephrine = beta_act * 40.0
        substance_p = max(0.0, 20.0 * (1.0 - g_act))

        return {
            'endorphins': endorphins,
            'dopamine': dopamine,
            'serotonin': serotonin,
            'norepinephrine': norepinephrine,
            'substance_p': substance_p,
        }



class CompoundAnalyzer:
    """Analysis tools for compound evaluation"""

    def __init__(self, database: CompoundDatabase):
        self.database = database
        self.pk_model = PharmacokineticModel()

    def compare_compounds(self, compound_names: List[str]) -> Dict:
        """Compare multiple compounds across key metrics"""
        results = {}

        for name in compound_names:
            compound = self.database.get_compound(name)
            if not compound:
                continue

            results[name] = {
                'safety_score': compound.calculate_safety_score(),
                'bias_ratio': compound.get_bias_ratio(),
                'ki_orthosteric': compound.ki_orthosteric,
                'ki_allosteric1': compound.ki_allosteric1,
                't_half': compound.t_half,
                'bioavailability': compound.bioavailability,
                'tolerance_rate': compound.tolerance_rate
            }

        return results

    def simulate_dose_response(self, compound_name: str, dose_range: np.ndarray,
                              time: float = 2.0) -> Dict:
        """Simulate dose-response curve

        Args:
            compound_name: Name of compound
            dose_range: Array of doses to test (mg)
            time: Time point for measurement (hours)

        Returns:
            Dictionary with dose-response data
        """
        compound = self.database.get_compound(compound_name)
        if not compound:
            return {}

        concentrations = []
        analgesia = []
        side_effects = []

        for dose in dose_range:
            # Calculate concentration
            conc = self.pk_model.calculate_concentration(
                dose, time, compound.t_half, compound.bioavailability
            )
            concentrations.append(conc)

            # Calculate receptor activation
            g_activation = self.pk_model.calculate_receptor_occupancy(
                conc, compound.ki_orthosteric,
                compound.intrinsic_activity * compound.g_protein_bias
            )

            beta_activation = self.pk_model.calculate_receptor_occupancy(
                conc, compound.ki_orthosteric,
                compound.intrinsic_activity * compound.beta_arrestin_bias
            )

            # Calculate effects
            analgesia.append(self.pk_model.calculate_analgesia(g_activation))
            side_effects.append(beta_activation)

        return {
            'doses': dose_range,
            'concentrations': np.array(concentrations),
            'analgesia': np.array(analgesia),
            'side_effects': np.array(side_effects),
            'therapeutic_window': self._calculate_therapeutic_window(
                np.array(analgesia), np.array(side_effects)
            )
        }

    def _calculate_therapeutic_window(self, analgesia: np.ndarray,
                                     side_effects: np.ndarray) -> float:
        """Calculate therapeutic window"""
        # Find ED50 for analgesia
        ed50_idx = np.argmin(np.abs(analgesia - 0.5))
        if ed50_idx >= len(side_effects):
            return float('inf')

        # Find TD50 for side effects
        td50_idx = np.argmin(np.abs(side_effects - 0.5))

        if ed50_idx == 0:
            return float('inf')

        return td50_idx / max(ed50_idx, 1)


# Initialize global database
COMPOUND_DB = CompoundDatabase()


if __name__ == '__main__':
    print("ZeroPain Opioid Analysis Tools")
    print("=" * 50)

    db = CompoundDatabase()
    analyzer = CompoundAnalyzer(db)

    # List all compounds
    print("\nAvailable Compounds:")
    for name in db.list_compounds():
        compound = db.get_compound(name)
        safety = compound.calculate_safety_score()
        print(f"  {name:20s} - Safety: {safety:5.1f} - Bias: {compound.get_bias_ratio():6.1f}x")

    # Filter by safety
    print("\n\nHigh Safety Compounds (>80):")
    safe_compounds = db.filter_by_safety(80.0)
    for compound in safe_compounds:
        print(f"  {compound.name:20s} - {compound.calculate_safety_score():.1f}")

    # Compare compounds
    print("\n\nComparing SR-17018, Oxycodone, Morphine:")
    comparison = analyzer.compare_compounds(['SR-17018', 'Oxycodone', 'Morphine'])
    for name, metrics in comparison.items():
        print(f"\n{name}:")
        for metric, value in metrics.items():
            print(f"  {metric:20s}: {value}")
