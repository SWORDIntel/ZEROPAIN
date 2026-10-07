import numpy as np

from research.human_sim.disposition import synthetic_reference_disposition
from research.human_sim.disposition import synthetic_reference_disposition
from research.human_sim.engine import simulate_human_chain, synthetic_target_panel
from research.human_sim.physiology import synthetic_reference_physiology


def test_full_chain_produces_bounded_target_states_and_mass_balance():
    result = simulate_human_chain(
        synthetic_reference_physiology(),
        synthetic_reference_disposition(),
        synthetic_target_panel(),
        duration_h=8.0,
        dt_h=0.05,
        initial_central_amount=1.0,
    )
    assert np.max(np.abs(result.pbpk.mass_balance_error)) < 1e-10

    for trace in result.targets.values():
        assert np.all((0.0 <= trace.occupancy) & (trace.occupancy <= 1.0))
        assert np.all((0.0 <= trace.signal_magnitude) & (trace.signal_magnitude <= 1.0))
        assert np.all((0.0 <= trace.surface_fraction) & (trace.surface_fraction <= 1.0))
        assert np.all((0.0 <= trace.coupling_fraction) & (trace.coupling_fraction <= 1.0))


def test_same_brain_exposure_yields_target_specific_occupancy():
    result = simulate_human_chain(
        synthetic_reference_physiology(),
        synthetic_reference_disposition(),
        synthetic_target_panel(),
        duration_h=2.0,
        dt_h=0.02,
        initial_central_amount=1.0,
    )
    peaks = {
        name: trace.occupancy.max()
        for name, trace in result.targets.items()
    }
    assert peaks["MOR_SYNTH"] > peaks["NMDAR_SYNTH"]


def test_trace_export_contains_pbpk_and_receptor_history():
    result = simulate_human_chain(
        synthetic_reference_physiology(),
        synthetic_reference_disposition(),
        synthetic_target_panel(),
        duration_h=1.0,
        dt_h=0.1,
        initial_central_amount=0.5,
    )
    payload = result.to_dict(include_trace=True)
    assert "pbpk" in payload["summary"]
    assert "trace" in payload
    assert "brain_free_concentration" in payload["trace"]
    assert set(payload["trace"]["targets"]) == set(synthetic_target_panel())
