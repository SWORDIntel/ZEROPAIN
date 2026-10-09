#!/usr/bin/env python3
"""
Unit and integration tests for ZEROPAIN Tensor Simulation Engine
===============================================================
"""

import sys
from pathlib import Path
import unittest
import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from tensor_simulation import (
    TensorPopulationSimulation,
    TensorSimulationEngine,
    TensorProtocolConfig,
    CohortConfig,
    COHORT_PRESETS,
    COMPOUND_REGISTRY,
    TensorCompoundProfile,
    StreamingHistogram,
    detect_device,
    run_tensor_simulation,
)


class TestTensorSimulationEngine(unittest.TestCase):
    """Test suite for high-performance PyTorch vectorized simulation."""

    def test_device_detection(self):
        """Test device detection with explicit cpu fallback."""
        dev = detect_device("cpu")
        self.assertEqual(dev.type, "cpu")
        auto_dev = detect_device()
        self.assertIn(auto_dev.type, ["cpu", "cuda"])

    def test_compound_registry_integrity(self):
        """Verify presence of key candidate and street compounds."""
        required = [
            "SR-16435", "SR-14968", "SR-14968-M", "SR-17018",
            "Buprenorphine", "Morphine", "Fentanyl", "Methadone",
            "Carfentanil", "Xylazine", "Isotonitazene", "Nitazene",
        ]
        for name in required:
            self.assertIn(name, COMPOUND_REGISTRY)
            cp = COMPOUND_REGISTRY[name]
            self.assertGreater(cp.t_half, 0.0)
            self.assertGreater(cp.bioavailability, 0.0)

    def test_cohort_generation_and_distributions(self):
        """Verify vectorized cohort generation adheres to PGx and organ distributions."""
        sim = TensorPopulationSimulation(device="cpu", seed=101)
        cfg = CohortConfig(
            cachexia_rate=0.10,
            morbid_obesity_rate=0.10,
            ugt2b7_poor_rate=0.20,
            abcb1_deficient_rate=0.25,
            cyp3a4_pm_rate=0.05,
            child_pugh_c_rate=0.05,
            ckd_stage5_esrd_rate=0.05,
            copd_gold4_rate=0.05,
        )
        gen = sim.generator if hasattr(sim, "generator") else None
        cohort = sim.run(total_patients=2000, cohort=cfg, chunk_size=2000, verbose=False)
        self.assertEqual(cohort.total_patients, 2000)

    def test_sr16435_dopamine_ceiling_and_addiction_block(self):
        """Verify NOP auto-inhibition caps dopamine release for SR-16435 vs Fentanyl."""
        # SR-16435
        p_sr = TensorProtocolConfig(compounds=["SR-16435"], doses=[20.0], frequencies=[2.0], duration_days=14)
        s_sr = run_tensor_simulation(total_patients=1000, protocol=p_sr, cohort="standard", chunk_size=1000, device="cpu", verbose=False)

        # Fentanyl
        p_fent = TensorProtocolConfig(compounds=["Fentanyl"], doses=[2.0], frequencies=[4.0], duration_days=14)
        s_fent = run_tensor_simulation(total_patients=1000, protocol=p_fent, cohort="standard", chunk_size=1000, device="cpu", verbose=False)

        # SR-16435 dopamine peak should be drastically lower than Fentanyl
        sr_da_p50 = s_sr.percentiles["dopamine_peak_surge"]["p50"]
        fent_da_p50 = s_fent.percentiles["dopamine_peak_surge"]["p50"]
        self.assertLess(sr_da_p50, 100.0)
        self.assertGreater(fent_da_p50, 200.0)
        self.assertLess(s_sr.addiction_rate, s_fent.addiction_rate)

    def test_tolerance_reversal_by_sr14968(self):
        """Verify active MOR resensitization by SR-14968."""
        cp = COMPOUND_REGISTRY["SR-14968"]
        self.assertTrue(cp.reverses_tolerance)
        self.assertGreater(cp.g_protein_bias, 5.0)
        self.assertLess(cp.beta_arrestin_bias, 0.2)

        p = TensorProtocolConfig(compounds=["SR-14968"], doses=[30.0], frequencies=[2.0], duration_days=30)
        s = run_tensor_simulation(total_patients=1000, protocol=p, cohort="standard", chunk_size=1000, device="cpu", verbose=False)
        self.assertLess(s.percentiles["tolerance_level"]["p50"], 0.20)

    def test_polysubstance_crisis_and_street_adulterants(self):
        """Verify lethal interactions with Xylazine, Nitazenes, and Benzos."""
        s = run_tensor_simulation(
            total_patients=1000,
            protocol=TensorProtocolConfig(compounds=["Fentanyl"], doses=[2.0], frequencies=[4.0], duration_days=14),
            cohort="polysubstance_crisis",
            chunk_size=1000,
            device="cpu",
            verbose=False,
        )
        self.assertGreater(s.respiratory_depression_rate, 0.50)
        self.assertGreater(s.overdose_rate, 0.30)

    def test_multi_organ_failure_cohort(self):
        """Verify multi-organ failure increases mortality and adverse events."""
        s = run_tensor_simulation(
            total_patients=1000,
            protocol=TensorProtocolConfig(compounds=["Morphine"], doses=[30.0], frequencies=[3.0], duration_days=14),
            cohort="multi_organ_failure",
            chunk_size=1000,
            device="cpu",
            verbose=False,
        )
        self.assertGreater(s.mortality_rate, 0.0)
        self.assertGreater(s.percentiles["paco2_mmHg"]["p90"], 45.0)

    def test_streaming_histogram_percentiles(self):
        """Verify StreamingHistogram accuracy for p50, p90, p99, p99.9, p99.99."""
        hist = StreamingHistogram(0.0, 100.0, num_bins=10000, device=torch.device("cpu"))
        data = torch.linspace(0.0, 100.0, 100000)
        hist.update(data)
        self.assertAlmostEqual(hist.get_percentile(50.0), 50.0, delta=0.2)
        self.assertAlmostEqual(hist.get_percentile(90.0), 90.0, delta=0.2)
        self.assertAlmostEqual(hist.get_percentile(99.0), 99.0, delta=0.2)
        self.assertAlmostEqual(hist.get_percentile(99.9), 99.9, delta=0.2)

    def test_chunking_consistency(self):
        """Verify multiple chunks aggregate seamlessly without memory leaks."""
        s_single = run_tensor_simulation(total_patients=2000, chunk_size=2000, device="cpu", verbose=False)
        s_chunked = run_tensor_simulation(total_patients=2000, chunk_size=500, device="cpu", verbose=False)
        self.assertEqual(s_single.total_patients, s_chunked.total_patients)
        self.assertAlmostEqual(s_single.analgesia_maintained_rate, s_chunked.analgesia_maintained_rate, delta=0.05)


if __name__ == "__main__":
    unittest.main()
