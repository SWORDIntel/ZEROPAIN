import unittest
import numpy as np
from opioid_analysis_tools import CompoundProfile, CompoundDatabase
from tolerance_models import LinearAddiction, AddictionState, LinearTolerance, make_addiction_model
from patient_simulation import PatientGenerator, PatientSimulator, PatientGenerationConfig, ProtocolConfig, PatientProfile
from dsmil_adapter import process_request

class NewFeaturesTests(unittest.TestCase):
    def test_compound_profile_new_affinities(self):
        c = CompoundProfile(
            name="TestOpioid",
            ki_orthosteric=10.0,
            ki_allosteric1=float('inf'),
            ki_allosteric2=float('inf'),
            g_protein_bias=1.0,
            beta_arrestin_bias=1.0,
            t_half=4.0,
            bioavailability=0.8,
            intrinsic_activity=0.8,
            tolerance_rate=0.2,
            prevents_withdrawal=False,
            reverses_tolerance=False,
            receptor_type="MOR",
            ki_mor=5.0,
            ki_dor=100.0,
            ki_kor=float('inf'),
            metabolic_pathways={"CYP2D6": 0.8, "CYP3A4": 0.2}
        )
        self.assertEqual(c.ki_mor, 5.0)
        self.assertEqual(c.ki_dor, 100.0)
        self.assertEqual(c.ki_kor, float('inf'))
        self.assertEqual(c.metabolic_pathways["CYP2D6"], 0.8)
        
        # Test serialization
        d = c.to_dict()
        self.assertEqual(d["ki_mor"], 5.0)
        self.assertEqual(d["metabolic_pathways"]["CYP3A4"], 0.2)
        
        c2 = CompoundProfile.from_dict(d)
        self.assertEqual(c2.ki_mor, 5.0)
        self.assertEqual(c2.ki_dor, 100.0)
        self.assertEqual(c2.metabolic_pathways["CYP2D6"], 0.8)

    def test_addiction_progression_model(self):
        model = make_addiction_model({
            "addiction_model": "linear",
            "addiction_slope": 0.1,
            "addiction_threshold": 1.0
        })
        self.assertIsInstance(model, LinearAddiction)
        
        state = AddictionState(level=0.0, threshold=1.0)
        dt = 0.25 / 24.0
        for _ in range(10):
            state = model.update(state, dopamine_release=2.0, dt_days=dt)
            
        self.assertGreater(state.level, 0.0)
        self.assertAlmostEqual(state.level, 0.010416666, places=5)

    def test_patient_specific_cyp_clearance(self):
        p_base = PatientProfile(
            patient_id=1,
            age=40,
            weight=70.0,
            sex="M",
            metabolism_rate=1.0,
            sensitivity=1.0,
            pain_severity=5.0,
            comorbidities=[],
            medications=[],
            baseline_tolerance=0.0,
            medication_effects={"metabolism_multiplier": 1.0},
            cyp_activity={"CYP2D6": 1.0, "CYP3A4": 1.0}
        )
        
        p_liver = PatientProfile(
            patient_id=2,
            age=40,
            weight=70.0,
            sex="M",
            metabolism_rate=0.6,
            sensitivity=1.0,
            pain_severity=5.0,
            comorbidities=["liver_disease"],
            medications=[],
            baseline_tolerance=0.0,
            medication_effects={"metabolism_multiplier": 1.0},
            cyp_activity={"CYP2D6": 0.6, "CYP3A4": 0.6}
        )
        
        c = CompoundProfile(
            name="C1",
            ki_orthosteric=10.0,
            ki_allosteric1=float('inf'),
            ki_allosteric2=float('inf'),
            g_protein_bias=1.0,
            beta_arrestin_bias=1.0,
            t_half=8.0,
            bioavailability=1.0,
            intrinsic_activity=1.0,
            tolerance_rate=0.2,
            prevents_withdrawal=False,
            reverses_tolerance=False,
            ki_mor=10.0,
            ki_dor=float('inf'),
            ki_kor=float('inf'),
            metabolic_pathways={"CYP2D6": 0.5, "CYP3A4": 0.5}
        )
        
        # Test CYP activity rate adjustment logic
        pathways = getattr(c, 'metabolic_pathways', {"CYP2D6": 0.5, "CYP3A4": 0.5})
        
        # Base Patient
        pathway_sum_base = sum(ratio * p_base.cyp_activity.get(enzyme, 1.0) for enzyme, ratio in pathways.items())
        adjusted_t_half_base = c.t_half / pathway_sum_base
        self.assertAlmostEqual(adjusted_t_half_base, 8.0)
        
        # Liver Patient
        pathway_sum_liver = sum(ratio * p_liver.cyp_activity.get(enzyme, 1.0) for enzyme, ratio in pathways.items())
        adjusted_t_half_liver = c.t_half / pathway_sum_liver
        self.assertAlmostEqual(adjusted_t_half_liver, 13.333333, places=5)

    def test_dsmil_adapter_request(self):
        db = CompoundDatabase()
        payload = {
            "operation": "simulate",
            "custom_compounds": [],
            "protocol": {
                "compounds": ["SR-17018", "SR-14968"],
                "doses": [16.0, 25.0],
                "frequencies": [2, 1]
            },
            "patient_count": 10,
            "patient_generation_config": {
                "population_size": 10,
            },
            "tolerance_config": {
                "model": "linear",
                "slope": 0.01,
                "addiction_model": "linear",
                "addiction_slope": 0.05
            }
        }

        res = process_request(payload)
        self.assertTrue(res.get("ok"), msg=res.get("error", "unknown error"))
        result = res["result"]
        self.assertIn("success_rate", result)
        self.assertIn("avg_pain_score", result)
        self.assertGreaterEqual(result["success_rate"], 0.0)

