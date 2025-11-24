import sys
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from patient_simulation_100k import (
    PatientGenerator,
    PatientGenerationConfig,
    AgeDistribution,
    MedicationProfile,
)
from opioid_analysis_tools import PharmacokineticModel


class PatientGenerationTests(unittest.TestCase):
    def test_age_distribution_respects_bounds(self):
        cfg = PatientGenerationConfig(
            population_size=200,
            age_distribution=AgeDistribution(
                alpha=2.0, beta=2.0, min_age=30, max_age=40
            ),
        )
        patients = PatientGenerator.generate_population(200, seed=123, config=cfg)
        ages = [p.age for p in patients]
        self.assertGreaterEqual(min(ages), 30)
        self.assertLessEqual(max(ages), 40)

    def test_comorbidity_prevalence_can_be_raised(self):
        high_prevalence = {"depression": 0.9, "anxiety": 0.9}
        cfg = PatientGenerationConfig(
            population_size=300,
            comorbidity_prevalence={
                **PatientGenerationConfig().comorbidity_prevalence,
                **high_prevalence,
            },
        )
        patients = PatientGenerator.generate_population(300, seed=321, config=cfg)
        depression_rate = np.mean(["depression" in p.comorbidities for p in patients])
        self.assertGreater(depression_rate, 0.75)

    def test_medication_prevalence_and_effects(self):
        med_cfg = PatientGenerationConfig(
            population_size=200,
            pre_existing_medications={
                "gabapentinoid": MedicationProfile(
                    name="Gabapentinoid",
                    prevalence=0.9,
                    analgesia_bonus=0.1,
                    baseline_tolerance=0.05,
                )
            },
        )
        patients = PatientGenerator.generate_population(200, seed=99, config=med_cfg)
        exposure_rate = np.mean([len(p.medications) > 0 for p in patients])
        self.assertGreater(exposure_rate, 0.8)
        self.assertGreater(np.mean([p.baseline_tolerance for p in patients]), 0.02)

    def test_neurotransmitter_release_quantified(self):
        releases = PharmacokineticModel.calculate_neurotransmitter_release(0.6, 0.2)
        expected_keys = {
            "endorphins",
            "dopamine",
            "serotonin",
            "norepinephrine",
            "substance_p",
        }
        self.assertEqual(set(releases.keys()), expected_keys)
        self.assertTrue(all(value >= 0 for value in releases.values()))
