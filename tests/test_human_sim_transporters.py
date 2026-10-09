import numpy as np

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.pbpk import simulate_pbpk
from research.human_sim.pbpk_reference import (
    compare_to_reference,
    simulate_pbpk_reference,
)
from research.human_sim.physiology import Physiology, TissueSpec
from research.human_sim.transporters import (
    TransportRoute,
    TransporterProcess,
    apply_transporter_step,
    michaelis_menten_rate,
)


def _physiology():
    return Physiology(
        central_volume_l=1.0,
        tissues=(
            TissueSpec("brain", 1.0, 0.0),
            TissueSpec("liver", 1.0, 0.0),
            TissueSpec("kidney", 1.0, 0.0),
            TissueSpec("peripheral", 1.0, 0.0),
        ),
        label="transporter_test",
    )


def _base_disposition(processes=()):
    return CompoundDisposition(
        label="transporter_fixture",
        tissue_partition_coefficients={
            "brain": 1.0,
            "liver": 1.0,
            "kidney": 1.0,
            "peripheral": 1.0,
        },
        plasma_unbound_fraction=0.5,
        brain_unbound_fraction=0.5,
        blood_to_plasma_ratio=1.0,
        transporter_processes=tuple(processes),
    )


def test_michaelis_menten_rate_has_expected_half_max_and_saturation():
    assert np.isclose(
        michaelis_menten_rate(
            2.0,
            vmax_amount_per_h=10.0,
            km_concentration=2.0,
        ),
        5.0,
    )
    saturated = michaelis_menten_rate(
        1e9,
        vmax_amount_per_h=10.0,
        km_concentration=2.0,
    )
    assert saturated < 10.0
    assert saturated > 9.999999


def test_hepatic_uptake_transfers_central_to_liver_and_conserves_mass():
    process = TransporterProcess(
        name="OATP_like",
        route=TransportRoute.HEPATIC_UPTAKE,
        vmax_amount_per_h=1.0,
        km_concentration=0.5,
        source_id="synthetic_fixture",
        transporter_family="OATP-like",
    )
    central, tissues, eliminated, fluxes = apply_transporter_step(
        central_amount=1.0,
        tissue_amounts={"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
        eliminated_amount=0.0,
        physiology=_physiology(),
        processes=(process,),
        plasma_unbound_fraction=0.5,
        blood_to_plasma_ratio=1.0,
        dt_h=0.5,
    )
    assert central < 1.0
    assert tissues["liver"] > 0.0
    assert np.isclose(
        central + sum(tissues.values()) + eliminated,
        1.0,
        atol=1e-12,
    )
    assert fluxes[0].source == "central"
    assert fluxes[0].sink == "liver"


def test_multiple_outgoing_routes_are_scaled_to_available_source_amount():
    processes = (
        TransporterProcess(
            name="uptake",
            route="hepatic_uptake",
            vmax_amount_per_h=100.0,
            km_concentration=0.001,
            source_id="synthetic_fixture",
        ),
        TransporterProcess(
            name="renal_uptake",
            route="renal_uptake",
            vmax_amount_per_h=100.0,
            km_concentration=0.001,
            source_id="synthetic_fixture",
        ),
    )
    central, tissues, eliminated, fluxes = apply_transporter_step(
        central_amount=0.1,
        tissue_amounts={"brain": 0.0, "liver": 0.0, "kidney": 0.0, "peripheral": 0.0},
        eliminated_amount=0.0,
        physiology=_physiology(),
        processes=processes,
        plasma_unbound_fraction=1.0,
        blood_to_plasma_ratio=1.0,
        dt_h=1.0,
    )
    assert central >= 0.0
    assert np.isclose(sum(f.transferred_amount for f in fluxes), 0.1, atol=1e-12)
    assert np.isclose(
        central + sum(tissues.values()) + eliminated,
        0.1,
        atol=1e-12,
    )


def test_biliary_and_renal_efflux_remove_tissue_amount_to_eliminated_pool():
    processes = (
        TransporterProcess(
            name="biliary",
            route="biliary_efflux",
            vmax_amount_per_h=0.5,
            km_concentration=0.2,
            source_unbound_fraction=0.5,
            source_id="synthetic_fixture",
        ),
        TransporterProcess(
            name="renal_secretory_efflux",
            route="renal_efflux_to_urine",
            vmax_amount_per_h=0.5,
            km_concentration=0.2,
            source_unbound_fraction=0.5,
            source_id="synthetic_fixture",
        ),
    )
    central, tissues, eliminated, _ = apply_transporter_step(
        central_amount=0.0,
        tissue_amounts={"brain": 0.0, "liver": 1.0, "kidney": 1.0, "peripheral": 0.0},
        eliminated_amount=0.0,
        physiology=_physiology(),
        processes=processes,
        plasma_unbound_fraction=1.0,
        blood_to_plasma_ratio=1.0,
        dt_h=0.5,
    )
    assert tissues["liver"] < 1.0
    assert tissues["kidney"] < 1.0
    assert eliminated > 0.0
    assert np.isclose(
        central + sum(tissues.values()) + eliminated,
        2.0,
        atol=1e-12,
    )


def test_tubular_reabsorption_returns_kidney_amount_to_central():
    process = TransporterProcess(
        name="reabsorption",
        route="tubular_reabsorption",
        vmax_amount_per_h=0.5,
        km_concentration=0.2,
        source_unbound_fraction=0.5,
        source_id="synthetic_fixture",
    )
    central, tissues, eliminated, _ = apply_transporter_step(
        central_amount=0.0,
        tissue_amounts={"brain": 0.0, "liver": 0.0, "kidney": 1.0, "peripheral": 0.0},
        eliminated_amount=0.0,
        physiology=_physiology(),
        processes=(process,),
        plasma_unbound_fraction=1.0,
        blood_to_plasma_ratio=1.0,
        dt_h=0.5,
    )
    assert central > 0.0
    assert tissues["kidney"] < 1.0
    assert eliminated == 0.0


def test_primary_and_rk4_reference_agree_with_active_transporters():
    physiology = Physiology(
        central_volume_l=5.0,
        tissues=(
            TissueSpec("brain", 1.4, 40.0),
            TissueSpec("liver", 1.8, 75.0),
            TissueSpec("kidney", 0.35, 55.0),
            TissueSpec("peripheral", 30.0, 60.0),
        ),
        label="reference_transport_test",
    )
    processes = (
        TransporterProcess(
            name="hepatic_uptake",
            route="hepatic_uptake",
            vmax_amount_per_h=0.15,
            km_concentration=0.05,
            source_id="synthetic_fixture",
        ),
        TransporterProcess(
            name="biliary_efflux",
            route="biliary_efflux",
            vmax_amount_per_h=0.05,
            km_concentration=0.04,
            source_unbound_fraction=0.2,
            source_id="synthetic_fixture",
        ),
        TransporterProcess(
            name="renal_uptake",
            route="renal_uptake",
            vmax_amount_per_h=0.08,
            km_concentration=0.05,
            source_id="synthetic_fixture",
        ),
        TransporterProcess(
            name="renal_efflux",
            route="renal_efflux_to_urine",
            vmax_amount_per_h=0.04,
            km_concentration=0.04,
            source_unbound_fraction=0.3,
            source_id="synthetic_fixture",
        ),
    )
    disposition = CompoundDisposition(
        label="active_transport_reference",
        tissue_partition_coefficients={
            "brain": 1.2,
            "liver": 2.0,
            "kidney": 1.4,
            "peripheral": 1.8,
        },
        plasma_unbound_fraction=0.4,
        brain_unbound_fraction=0.3,
        blood_to_plasma_ratio=1.1,
        transporter_processes=processes,
    )

    primary = simulate_pbpk(
        physiology,
        disposition,
        duration_h=2.0,
        dt_h=0.01,
        initial_central_amount=1.0,
    )
    reference = simulate_pbpk_reference(
        physiology,
        disposition,
        duration_h=2.0,
        output_dt_h=0.01,
        substeps=30,
        initial_central_amount=1.0,
    )
    comparison = compare_to_reference(primary, reference)
    assert comparison.max_metric < 0.05, comparison.to_dict()
    assert primary.eliminated_amount[-1] > 0.0
    assert np.max(np.abs(primary.mass_balance_error)) < 1e-10
