import numpy as np

from research.human_sim.competition import LigandInteraction, competitive_state
from research.human_sim.disposition import CompoundDisposition, synthetic_reference_disposition
from research.human_sim.multiligand_engine import LigandSpec, simulate_multiligand_chain
from research.human_sim.physiology import synthetic_reference_physiology


def test_competitive_occupancies_plus_unbound_sum_to_one():
    interactions = {
        "agonist": LigandInteraction("agonist", 0.2, efficacy=1.0),
        "antagonist": LigandInteraction("antagonist", 0.1, efficacy=0.0),
    }
    state = competitive_state(
        {"agonist": 0.5, "antagonist": 0.5},
        interactions,
    )
    total = state.unbound_fraction + sum(state.occupancy_by_ligand.values())
    assert np.isclose(total, 1.0)


def test_antagonist_occupancy_reduces_agonist_signal():
    agonist_only = competitive_state(
        {"agonist": 0.5},
        {"agonist": LigandInteraction("agonist", 0.2, efficacy=1.0)},
    )
    competed = competitive_state(
        {"agonist": 0.5, "antagonist": 0.5},
        {
            "agonist": LigandInteraction("agonist", 0.2, efficacy=1.0),
            "antagonist": LigandInteraction("antagonist", 0.05, efficacy=0.0),
        },
    )
    assert competed.signal_magnitude < agonist_only.signal_magnitude
    assert competed.occupancy_by_ligand["antagonist"] > 0


def test_partial_agonist_has_lower_signal_than_full_agonist_at_same_binding():
    full = competitive_state(
        {"x": 0.5},
        {"x": LigandInteraction("x", 0.2, efficacy=1.0)},
    )
    partial = competitive_state(
        {"x": 0.5},
        {"x": LigandInteraction("x", 0.2, efficacy=0.35)},
    )
    assert np.isclose(full.occupancy_by_ligand["x"], partial.occupancy_by_ligand["x"])
    assert partial.signal_magnitude < full.signal_magnitude


def _ligand(name, efficacy, kd):
    base = synthetic_reference_disposition()
    disposition = CompoundDisposition(
        label=name,
        tissue_partition_coefficients=dict(base.tissue_partition_coefficients),
        brain_unbound_fraction=base.brain_unbound_fraction,
    )
    return LigandSpec(
        name=name,
        disposition=disposition,
        target_interactions={
            "MOR_SYNTH": LigandInteraction(name, kd, efficacy=efficacy),
        },
    )


def test_multiligand_engine_preserves_mass_and_competitive_bounds():
    ligands = {
        "agonist": _ligand("agonist", 0.8, 0.15),
        "antagonist": _ligand("antagonist", 0.0, 0.08),
    }
    result = simulate_multiligand_chain(
        synthetic_reference_physiology(),
        ligands,
        initial_central_amounts={"agonist": 1.0, "antagonist": 0.8},
        duration_h=4.0,
        dt_h=0.05,
    )
    for trace in result.pbpk_by_ligand.values():
        assert np.max(np.abs(trace.mass_balance_error)) < 1e-10

    target = result.targets["MOR_SYNTH"]
    summed = target.unbound_fraction.copy()
    for occupancy in target.occupancy_by_ligand.values():
        summed = summed + occupancy
    assert np.allclose(summed, 1.0)
    assert np.all((0 <= target.signal_magnitude) & (target.signal_magnitude <= 1))


def test_multiligand_antagonist_reduces_integrated_target_signal():
    physiology = synthetic_reference_physiology()
    agonist = {"agonist": _ligand("agonist", 0.8, 0.15)}
    combo = {
        "agonist": _ligand("agonist", 0.8, 0.15),
        "antagonist": _ligand("antagonist", 0.0, 0.05),
    }
    control = simulate_multiligand_chain(
        physiology,
        agonist,
        initial_central_amounts={"agonist": 1.0},
        duration_h=3.0,
        dt_h=0.05,
    )
    competed = simulate_multiligand_chain(
        physiology,
        combo,
        initial_central_amounts={"agonist": 1.0, "antagonist": 1.0},
        duration_h=3.0,
        dt_h=0.05,
    )
    assert (
        competed.targets["MOR_SYNTH"].signal_magnitude.mean()
        < control.targets["MOR_SYNTH"].signal_magnitude.mean()
    )
