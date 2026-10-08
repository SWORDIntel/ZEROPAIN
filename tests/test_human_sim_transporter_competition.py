import numpy as np
import pytest

from research.human_sim.coupled_pbpk import simulate_coupled_pbpk
from research.human_sim.coupled_pbpk_reference import (
    compare_coupled_to_reference,
    simulate_coupled_pbpk_reference,
)
from research.human_sim.disposition import CompoundDisposition
from research.human_sim.multiligand_engine import LigandSpec, simulate_multiligand_chain
from research.human_sim.competition import LigandInteraction
from research.human_sim.pbpk import simulate_pbpk
from research.human_sim.physiology import Physiology, TissueSpec
from research.human_sim.transporter_competition import (
    TransporterInhibition,
    apply_competitive_transporter_step,
    competitive_transporter_flux_rates,
)
from research.human_sim.transporters import TransporterProcess


def _physiology():
    return Physiology(
        central_volume_l=1.0,
        tissues=(
            TissueSpec("brain", 1.0, 0.0),
            TissueSpec("liver", 1.0, 0.0),
            TissueSpec("kidney", 1.0, 0.0),
            TissueSpec("peripheral", 1.0, 0.0),
        ),
        label="ddi_test",
    )


def _disposition(name, process=None):
    processes = () if process is None else (process,)
    return CompoundDisposition(
        label=name,
        tissue_partition_coefficients={
            "brain": 1.0,
            "liver": 1.0,
            "kidney": 1.0,
            "peripheral": 1.0,
        },
        plasma_unbound_fraction=1.0,
        brain_unbound_fraction=1.0,
        blood_to_plasma_ratio=1.0,
        transporter_processes=processes,
    )


def _uptake(name, *, group="hepatic_OATP1B1", vmax=1.0, km=1.0):
    return TransporterProcess(
        name=name,
        route="hepatic_uptake",
        vmax_amount_per_h=vmax,
        km_concentration=km,
        source_id="synthetic_fixture",
        transporter_family="OATP1B1-like",
        interaction_group=group,
    )


def test_two_substrates_share_hand_calculated_competitive_denominator():
    physiology = _physiology()
    dispositions = {
        "a": _disposition("a", _uptake("a_uptake")),
        "b": _disposition("b", _uptake("b_uptake")),
    }
    fluxes = competitive_transporter_flux_rates(
        central_amounts={"a": 1.0, "b": 1.0},
        tissue_amounts_by_ligand={
            "a": {"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
            "b": {"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
        },
        physiology=physiology,
        dispositions=dispositions,
    )
    rates = {flux.ligand_name: flux.requested_amount for flux in fluxes}
    # Each has C/Km=1. Shared denominator = 1 + 1 + 1 = 3.
    assert np.isclose(rates["a"], 1.0 / 3.0)
    assert np.isclose(rates["b"], 1.0 / 3.0)
    assert all(np.isclose(flux.denominator, 3.0) for flux in fluxes)


def test_inhibitor_only_compound_suppresses_victim_without_being_transported():
    physiology = _physiology()
    dispositions = {
        "victim": _disposition("victim", _uptake("victim_uptake")),
        "inhibitor": _disposition("inhibitor"),
    }
    inhibition = TransporterInhibition(
        inhibitor_name="inhibitor",
        interaction_group="hepatic_OATP1B1",
        ki_concentration=0.5,
        source_compartment="central",
        source_id="synthetic_fixture",
    )
    fluxes = competitive_transporter_flux_rates(
        central_amounts={"victim": 1.0, "inhibitor": 1.0},
        tissue_amounts_by_ligand={
            "victim": {"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
            "inhibitor": {"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
        },
        physiology=physiology,
        dispositions=dispositions,
        inhibitions_by_ligand={"inhibitor": (inhibition,)},
    )
    assert len(fluxes) == 1
    victim = fluxes[0]
    # substrate weight=1, inhibitor weight=1/0.5=2, denominator=4.
    assert np.isclose(victim.inhibitor_weight, 2.0)
    assert np.isclose(victim.denominator, 4.0)
    assert np.isclose(victim.requested_amount, 0.25)


def test_same_ligand_cannot_be_double_counted_as_substrate_and_explicit_inhibitor():
    physiology = _physiology()
    dispositions = {"x": _disposition("x", _uptake("x_uptake"))}
    inhibition = TransporterInhibition(
        inhibitor_name="x",
        interaction_group="hepatic_OATP1B1",
        ki_concentration=1.0,
        source_id="synthetic_fixture",
    )
    with pytest.raises(ValueError, match="both substrate and explicit inhibitor"):
        competitive_transporter_flux_rates(
            central_amounts={"x": 1.0},
            tissue_amounts_by_ligand={
                "x": {"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0}
            },
            physiology=physiology,
            dispositions=dispositions,
            inhibitions_by_ligand={"x": (inhibition,)},
        )


def test_competitive_step_conserves_mass_for_every_ligand():
    physiology = _physiology()
    dispositions = {
        "a": _disposition("a", _uptake("a_uptake", vmax=100.0, km=0.001)),
        "b": _disposition("b", _uptake("b_uptake", vmax=100.0, km=0.001)),
    }
    central, tissues, eliminated, fluxes = apply_competitive_transporter_step(
        central_amounts={"a": 0.1, "b": 0.2},
        tissue_amounts_by_ligand={
            "a": {"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
            "b": {"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
        },
        eliminated_amounts={"a": 0.0, "b": 0.0},
        physiology=physiology,
        dispositions=dispositions,
        dt_h=1.0,
    )
    assert central["a"] >= 0
    assert central["b"] >= 0
    assert np.isclose(central["a"] + sum(tissues["a"].values()) + eliminated["a"], 0.1)
    assert np.isclose(central["b"] + sum(tissues["b"].values()) + eliminated["b"], 0.2)
    assert all(flux.transferred_amount >= 0 for flux in fluxes)


def test_single_grouped_substrate_matches_single_compound_pbpk():
    physiology = _physiology()
    disposition = _disposition("x", _uptake("x_uptake", group="hepatic_OATP1B1"))

    single = simulate_pbpk(
        physiology,
        disposition,
        duration_h=1.0,
        dt_h=0.01,
        initial_central_amount=1.0,
    )
    coupled = simulate_coupled_pbpk(
        physiology,
        {"x": disposition},
        initial_central_amounts={"x": 1.0},
        duration_h=1.0,
        dt_h=0.01,
    )["x"]

    assert np.allclose(single.central_amount, coupled.central_amount, atol=1e-12)
    assert np.allclose(
        single.tissue_amounts["liver"],
        coupled.tissue_amounts["liver"],
        atol=1e-12,
    )
    assert np.max(np.abs(coupled.mass_balance_error)) < 1e-12


def test_transporter_inhibition_changes_pk_trajectory_in_multiligand_engine():
    physiology = Physiology(
        central_volume_l=5.0,
        tissues=(
            TissueSpec("brain", 1.4, 40.0),
            TissueSpec("liver", 1.8, 75.0),
            TissueSpec("kidney", 0.35, 55.0),
            TissueSpec("peripheral", 30.0, 60.0),
        ),
        label="ddi_full",
    )

    victim_disp = CompoundDisposition(
        label="victim",
        tissue_partition_coefficients={
            "brain": 1.2,
            "liver": 2.0,
            "kidney": 1.4,
            "peripheral": 1.8,
        },
        plasma_unbound_fraction=0.5,
        brain_unbound_fraction=0.5,
        transporter_processes=(
            _uptake("victim_oatp", vmax=0.3, km=0.05),
        ),
    )
    inhibitor_disp = CompoundDisposition(
        label="inhibitor",
        tissue_partition_coefficients={
            "brain": 1.0,
            "liver": 1.0,
            "kidney": 1.0,
            "peripheral": 1.0,
        },
        plasma_unbound_fraction=0.5,
        brain_unbound_fraction=0.5,
    )

    victim = LigandSpec(
        name="victim",
        disposition=victim_disp,
        target_interactions={
            "TARGET": LigandInteraction("victim", 0.2, efficacy=1.0)
        },
    )
    inhibitor = LigandSpec(
        name="inhibitor",
        disposition=inhibitor_disp,
        target_interactions={
            "TARGET": LigandInteraction("inhibitor", 10.0, efficacy=0.0)
        },
        transporter_inhibitions=(
            TransporterInhibition(
                inhibitor_name="inhibitor",
                interaction_group="hepatic_OATP1B1",
                ki_concentration=0.03,
                source_id="synthetic_fixture",
            ),
        ),
    )

    control = simulate_multiligand_chain(
        physiology,
        {"victim": victim},
        initial_central_amounts={"victim": 1.0},
        duration_h=1.0,
        dt_h=0.01,
    )
    inhibited = simulate_multiligand_chain(
        physiology,
        {"victim": victim, "inhibitor": inhibitor},
        initial_central_amounts={"victim": 1.0, "inhibitor": 1.0},
        duration_h=1.0,
        dt_h=0.01,
    )

    # Blocking hepatic uptake should retain more victim in central blood and less in liver.
    assert (
        inhibited.pbpk_by_ligand["victim"].central_amount[-1]
        > control.pbpk_by_ligand["victim"].central_amount[-1]
    )
    assert (
        inhibited.pbpk_by_ligand["victim"].tissue_amounts["liver"][-1]
        < control.pbpk_by_ligand["victim"].tissue_amounts["liver"][-1]
    )
    for trace in inhibited.pbpk_by_ligand.values():
        assert np.max(np.abs(trace.mass_balance_error)) < 1e-10



def test_coupled_production_matches_independent_rk4_for_substrate_competition():
    physiology = Physiology(
        central_volume_l=5.0,
        tissues=(
            TissueSpec("brain", 1.4, 40.0),
            TissueSpec("liver", 1.8, 75.0),
            TissueSpec("kidney", 0.35, 55.0),
            TissueSpec("peripheral", 30.0, 60.0),
        ),
        label="substrate_competition_reference",
    )
    dispositions = {
        "a": CompoundDisposition(
            label="a",
            tissue_partition_coefficients={
                "brain": 1.2, "liver": 2.0, "kidney": 1.4, "peripheral": 1.8,
            },
            plasma_unbound_fraction=0.5,
            brain_unbound_fraction=0.5,
            transporter_processes=(
                _uptake("a_oatp", vmax=0.25, km=0.06),
            ),
        ),
        "b": CompoundDisposition(
            label="b",
            tissue_partition_coefficients={
                "brain": 1.0, "liver": 1.7, "kidney": 1.2, "peripheral": 1.5,
            },
            plasma_unbound_fraction=0.4,
            brain_unbound_fraction=0.4,
            transporter_processes=(
                _uptake("b_oatp", vmax=0.18, km=0.04),
            ),
        ),
    }
    initial = {"a": 1.0, "b": 0.8}
    primary = simulate_coupled_pbpk(
        physiology,
        dispositions,
        initial_central_amounts=initial,
        duration_h=1.5,
        dt_h=0.01,
    )
    reference = simulate_coupled_pbpk_reference(
        physiology,
        dispositions,
        initial_central_amounts=initial,
        duration_h=1.5,
        output_dt_h=0.01,
        substeps=30,
    )
    comparison = compare_coupled_to_reference(primary, reference)
    assert comparison["max_metric"] < 0.05, comparison


def test_coupled_production_matches_independent_rk4_for_inhibitor_only_ddi():
    physiology = Physiology(
        central_volume_l=5.0,
        tissues=(
            TissueSpec("brain", 1.4, 40.0),
            TissueSpec("liver", 1.8, 75.0),
            TissueSpec("kidney", 0.35, 55.0),
            TissueSpec("peripheral", 30.0, 60.0),
        ),
        label="inhibitor_reference",
    )
    dispositions = {
        "victim": CompoundDisposition(
            label="victim",
            tissue_partition_coefficients={
                "brain": 1.2, "liver": 2.0, "kidney": 1.4, "peripheral": 1.8,
            },
            plasma_unbound_fraction=0.5,
            brain_unbound_fraction=0.5,
            transporter_processes=(
                _uptake("victim_oatp", vmax=0.30, km=0.05),
            ),
        ),
        "inhibitor": CompoundDisposition(
            label="inhibitor",
            tissue_partition_coefficients={
                "brain": 1.0, "liver": 1.0, "kidney": 1.0, "peripheral": 1.0,
            },
            plasma_unbound_fraction=0.5,
            brain_unbound_fraction=0.5,
        ),
    }
    inhibitions = {
        "inhibitor": (
            TransporterInhibition(
                inhibitor_name="inhibitor",
                interaction_group="hepatic_OATP1B1",
                ki_concentration=0.03,
                source_id="synthetic_fixture",
            ),
        )
    }
    initial = {"victim": 1.0, "inhibitor": 1.0}
    primary = simulate_coupled_pbpk(
        physiology,
        dispositions,
        initial_central_amounts=initial,
        duration_h=1.5,
        dt_h=0.01,
        inhibitions_by_ligand=inhibitions,
    )
    reference = simulate_coupled_pbpk_reference(
        physiology,
        dispositions,
        initial_central_amounts=initial,
        duration_h=1.5,
        output_dt_h=0.01,
        substeps=30,
        inhibitions_by_ligand=inhibitions,
    )
    comparison = compare_coupled_to_reference(primary, reference)
    assert comparison["max_metric"] < 0.05, comparison
