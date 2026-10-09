from research.dissociation.belief_phase_sweep import run_phase_sweep
from research.dissociation.belief_network import BeliefNetworkParameters


def test_phase_sweep_returns_all_profile_cells():
    result = run_phase_sweep(
        [0.25, 0.65],
        steps=80,
        n_states=4,
        seeds=2,
        sync_interval=20,
        base_seed=7,
    )
    assert len(result["rows"]) == 2 * 6
    assert result["direct_meth_misreport_weight"] == 0.0


def test_low_trust_has_more_false_reporting_than_high_trust_in_baseline():
    result = run_phase_sweep(
        [0.20, 0.80],
        steps=120,
        n_states=4,
        seeds=3,
        sync_interval=30,
        base_seed=11,
    )
    rows = {
        (row["profile"], row["initial_trust_mean"]): row
        for row in result["rows"]
    }
    low = rows[("baseline", 0.20)]
    high = rows[("baseline", 0.80)]
    assert low["mean_false_report_rate"] > high["mean_false_report_rate"]
    assert low["mean_withholding_rate"] > high["mean_withholding_rate"]


def test_direct_meth_false_report_term_is_explicit_sensitivity_not_default():
    default = run_phase_sweep(
        [0.55],
        steps=80,
        n_states=4,
        seeds=2,
        sync_interval=20,
        base_seed=13,
    )
    forced = run_phase_sweep(
        [0.55],
        steps=80,
        n_states=4,
        seeds=2,
        sync_interval=20,
        base_seed=13,
        base_params=BeliefNetworkParameters(direct_meth_misreport_weight=0.20),
    )

    def cell(result, profile):
        return next(row for row in result["rows"] if row["profile"] == profile)

    assert default["direct_meth_misreport_weight"] == 0.0
    assert forced["direct_meth_misreport_weight"] == 0.20
    assert (
        cell(forced, "meth")["mean_false_report_rate"]
        >= cell(default, "meth")["mean_false_report_rate"]
    )
