import numpy as np

from pkpd_calibration import PKPDConfig, PriorSpec, calibrate_pkpd
from tolerance_models import make_tolerance_model, ToleranceState
from scenarios import parse_cohort_spec, build_generation_config


def test_pkpd_calibration_map_basic():
    cfg = PKPDConfig(
        model="one_compartment",
        priors={
            "ka": PriorSpec(mu=0.0, sigma=0.3),
            "cl": PriorSpec(mu=2.0, sigma=0.3),
            "v": PriorSpec(mu=3.5, sigma=0.3),
        },
    )
    t = np.linspace(0, 24, 24)
    y = np.exp(-t / 8.0)
    result = calibrate_pkpd(cfg, {"time": t.tolist(), "conc": y.tolist(), "dose": 100.0})
    params = result["pk_summary"]["params"]
    assert params["ka"] > 0
    assert params["cl"] > 0
    assert params["v"] > 0


def test_tolerance_models_monotonic():
    tol_model = make_tolerance_model({"model": "sigmoid", "max_factor": 2.0, "half_life_days": 7})
    state = ToleranceState(level=0.0, ceiling=2.0)
    updated = tol_model.update(state, exposure=10.0, dt_days=7.0)
    assert 0.0 <= updated.level <= updated.ceiling


def test_scenario_cohort_generator():
    cohort = parse_cohort_spec("n=50,age=55±8,renal=0.2,seed=1")
    gen_cfg = build_generation_config(cohort)
    assert gen_cfg.population_size == 50
    assert 0.0 <= gen_cfg.comorbidity_prevalence["kidney_disease"] <= 1.0

