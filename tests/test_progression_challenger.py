import pytest
import numpy as np
from opioid_analysis_tools import CompoundDatabase
from patient_simulation import (
    PatientGenerator,
    PatientSimulator,
    PopulationSimulation,
    PatientGenerationConfig,
)
from tolerance_models import (
    make_tolerance_model,
    make_addiction_model,
    ToleranceState,
    AddictionState,
    LinearTolerance,
    SigmoidTolerance,
    LaggedTolerance,
)
from opioid_optimization_framework import ProtocolConfig
from dsmil_adapter import process_request


def test_tolerance_slope_impact():
    """
    Verify that increasing tolerance slope increases tolerance rate
    and decreases treatment success rate.
    """
    db = CompoundDatabase()
    sim = PopulationSimulation(db, use_multiprocessing=False)

    # Use a standard protocol with Oxycodone (known to induce tolerance/withdrawal)
    protocol = ProtocolConfig(
        compounds=["Oxycodone"],
        doses=[10.0],
        frequencies=[3]
    )

    # Configuration with low tolerance slope
    low_tol_config = {
        "tolerance": {
            "model": "linear",
            "slope": 0.001,
            "max_factor": 3.0,
            "addiction_slope": 0.005,
            "addiction_threshold": 60.0
        }
    }

    # Configuration with high tolerance slope
    high_tol_config = {
        "tolerance": {
            "model": "linear",
            "slope": 0.1,  # 100x higher
            "max_factor": 3.0,
            "addiction_slope": 0.005,
            "addiction_threshold": 60.0
        }
    }

    # Generate 100 patients to ensure a stable sample
    n_patients = 100
    seed = 42

    res_low = sim.run_simulation(
        protocol=protocol,
        n_patients=n_patients,
        duration_days=30,
        seed=seed,
        tolerance_config=low_tol_config
    )

    res_high = sim.run_simulation(
        protocol=protocol,
        n_patients=n_patients,
        duration_days=30,
        seed=seed,
        tolerance_config=high_tol_config
    )

    print(f"Low Tol Slope -> Success Rate: {res_low['success_rate']:.3f}, Tolerance Rate: {res_low['tolerance_rate']:.3f}")
    print(f"High Tol Slope -> Success Rate: {res_high['success_rate']:.3f}, Tolerance Rate: {res_high['tolerance_rate']:.3f}")

    # Confirm higher tolerance slope leads to higher tolerance development
    assert res_high['tolerance_rate'] >= res_low['tolerance_rate']
    # Confirm higher tolerance slope leads to equal or lower success rate
    assert res_high['success_rate'] <= res_low['success_rate']


def test_addiction_slope_impact():
    """
    Verify that increasing addiction slope increases addiction rate.
    """
    db = CompoundDatabase()
    sim = PopulationSimulation(db, use_multiprocessing=False)

    protocol = ProtocolConfig(
        compounds=["Oxycodone"],
        doses=[20.0],  # Higher dose to trigger dopamine release above threshold
        frequencies=[4]
    )

    # Configuration with low addiction slope
    low_add_config = {
        "tolerance": {
            "model": "linear",
            "slope": 0.01,
            "max_factor": 3.0,
            "addiction_slope": 0.0001,
            "addiction_threshold": 5.0  # low threshold to trigger addiction dynamics
        }
    }

    # Configuration with high addiction slope
    high_add_config = {
        "tolerance": {
            "model": "linear",
            "slope": 0.01,
            "max_factor": 3.0,
            "addiction_slope": 0.5,  # 5000x higher
            "addiction_threshold": 5.0
        }
    }

    n_patients = 100
    seed = 42

    res_low = sim.run_simulation(
        protocol=protocol,
        n_patients=n_patients,
        duration_days=10,
        seed=seed,
        tolerance_config=low_add_config
    )

    res_high = sim.run_simulation(
        protocol=protocol,
        n_patients=n_patients,
        duration_days=10,
        seed=seed,
        tolerance_config=high_add_config
    )

    print(f"Low Add Slope -> Addiction Rate: {res_low['addiction_rate']:.3f}")
    print(f"High Add Slope -> Addiction Rate: {res_high['addiction_rate']:.3f}")

    # Confirm higher addiction slope leads to higher addiction rate
    assert res_high['addiction_rate'] > res_low['addiction_rate']


def test_metabolic_parameters_impact():
    """
    Verify that patient metabolic rate changes affect simulation outcomes.
    Specifically, patients with kidney/liver disease have lower clearance rates,
    which should result in higher side effects and lower success rate for high dose.
    """
    db = CompoundDatabase()
    sim = PatientSimulator(db)

    # Create a compound that has significant CYP clearance
    protocol = ProtocolConfig(
        compounds=["Oxycodone"],
        doses=[15.0],
        frequencies=[3]
    )

    # Base patient (normal metabolism)
    p_base = PatientGenerator.generate_patient(patient_id=1, seed=123)
    p_base.metabolism_rate = 1.5
    p_base.cyp_activity = {"CYP2D6": 1.5, "CYP3A4": 1.5}
    p_base.comorbidities = []

    # Impaired patient (liver disease)
    p_impaired = PatientGenerator.generate_patient(patient_id=1, seed=123)
    p_impaired.metabolism_rate = 0.4
    p_impaired.cyp_activity = {"CYP2D6": 0.4, "CYP3A4": 0.4}
    p_impaired.comorbidities = ["liver_disease"]

    res_base = sim.simulate_patient(p_base, protocol, duration_days=5)
    res_impaired = sim.simulate_patient(p_impaired, protocol, duration_days=5)

    print(f"Normal Patient -> Side Effects: {res_base.avg_side_effects:.3f}, Success: {res_base.success}")
    print(f"Impaired Patient -> Side Effects: {res_impaired.avg_side_effects:.3f}, Success: {res_impaired.success}")

    # Impaired patient accumulates higher concentrations, leading to higher average side effects
    assert res_impaired.avg_side_effects > res_base.avg_side_effects


def test_dsmil_adapter_respects_tolerance_config():
    """
    Verify that process_request in dsmil_adapter respects tolerance_config.
    We compare two requests with vastly different tolerance slopes.
    If the adapter forwarded them, the results (like tolerance_rate) would differ.
    """
    db = CompoundDatabase()
    payload_low = {
        "compounds": [db.get_compound("Oxycodone").to_dict()],
        "protocol": {
            "compounds": ["Oxycodone"],
            "doses": [15.0],
            "frequencies": [3]
        },
        "n_patients_sim": 50,
        "seed": 42,
        "tolerance_config": {
            "tolerance": {
                "model": "linear",
                "slope": 0.00001,
                "max_factor": 3.0
            }
        }
    }

    payload_high = {
        "compounds": [db.get_compound("Oxycodone").to_dict()],
        "protocol": {
            "compounds": ["Oxycodone"],
            "doses": [15.0],
            "frequencies": [3]
        },
        "n_patients_sim": 50,
        "seed": 42,
        "tolerance_config": {
            "tolerance": {
                "model": "linear",
                "slope": 1.0,  # Extremely high
                "max_factor": 3.0
            }
        }
    }

    res_low = process_request(payload_low)
    res_high = process_request(payload_high)

    print(f"DSM_IL Low -> Tolerance Rate: {res_low['tolerance_rate']:.3f}")
    print(f"DSM_IL High -> Tolerance Rate: {res_high['tolerance_rate']:.3f}")

    # Assert that high tolerance slope leads to higher tolerance rate, confirming it is respected
    assert res_high['tolerance_rate'] > res_low['tolerance_rate']


def test_invalid_configurations_handling():
    """
    Verify how the models handle invalid/extreme configurations.
    """
    # 1. Non-dict tolerance_config passes to simulate_patient
    db = CompoundDatabase()
    sim = PopulationSimulation(db, use_multiprocessing=False)
    protocol = ProtocolConfig(compounds=["Oxycodone"], doses=[5.0], frequencies=[2])

    # If tolerance_config is a string instead of a Dict, it should fail with TypeError or AttributeError
    # Let's verify that it does indeed raise an exception (which is not handled gracefully)
    with pytest.raises((AttributeError, TypeError)):
        sim.run_simulation(
            protocol=protocol,
            n_patients=5,
            duration_days=5,
            tolerance_config="not_a_dictionary"
        )

    # 2. What if the tolerance model name is invalid?
    # Silently falls back to SigmoidTolerance in make_tolerance_model.
    model = make_tolerance_model({"model": "invalid_model_name", "max_factor": 5.0})
    assert isinstance(model, SigmoidTolerance)
    assert model.max_factor == 5.0

    # 3. Negative half-life or rise_tau (should be handled gracefully via max(..., 1e-3))
    model_sigmoid_neg = make_tolerance_model({"model": "sigmoid", "half_life_days": -10.0})
    assert model_sigmoid_neg.half_life_days == 1e-3

    model_lagged_neg = make_tolerance_model({"model": "lagged", "rise_tau": -5.0, "decay_tau": 0.0})
    assert model_lagged_neg.rise_tau == 1e-3
    assert model_lagged_neg.decay_tau == 1e-3
