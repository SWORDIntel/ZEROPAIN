"""Saturable transporter processes for HumanSim liver/kidney PBPK.

The transporter layer models directed *amount fluxes* rather than folding active
transport into a scalar clearance.

Supported routes:
- hepatic uptake: blood/plasma -> liver
- hepatic basolateral efflux: liver -> blood
- biliary efflux: liver -> eliminated
- renal uptake: blood/plasma -> kidney
- renal efflux/secretion: kidney -> eliminated
- tubular reabsorption: kidney -> blood

Kinetics use a Michaelis-Menten amount rate:

    rate = Vmax * Cu_source / (Km + Cu_source)

where Vmax is amount/hour and Km is concentration in the same arbitrary concentration
unit used by the PBPK model.

For blood/plasma-source routes, Cu_source is:
    Cblood * fu_plasma / (blood:plasma)

For tissue-source routes, an explicit source_unbound_fraction is required.

All routes are evaluated from the same pre-transport state, then outgoing requested
amounts are proportionally capped by source compartment amount. This preserves
non-negativity and exact mass conservation for the transporter operator.

No transporter parameter defaults represent a real drug.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping

import numpy as np

from research.human_sim.physiology import Physiology


class TransportRoute(str, Enum):
    HEPATIC_UPTAKE = "hepatic_uptake"
    HEPATIC_EFFLUX_TO_BLOOD = "hepatic_efflux_to_blood"
    BILIARY_EFFLUX = "biliary_efflux"
    RENAL_UPTAKE = "renal_uptake"
    RENAL_EFFLUX_TO_URINE = "renal_efflux_to_urine"
    TUBULAR_REABSORPTION = "tubular_reabsorption"


@dataclass(frozen=True)
class TransporterProcess:
    name: str
    route: TransportRoute | str
    vmax_amount_per_h: float
    km_concentration: float
    source_unbound_fraction: float | None = None
    source_id: str = ""
    transporter_family: str = ""

    def validate(self) -> None:
        if not self.name:
            raise ValueError("transporter process name cannot be blank")
        TransportRoute(self.route)
        if self.vmax_amount_per_h < 0:
            raise ValueError(f"{self.name}: Vmax cannot be negative")
        if self.km_concentration <= 0:
            raise ValueError(f"{self.name}: Km must be positive")
        route = TransportRoute(self.route)
        if route in {
            TransportRoute.HEPATIC_EFFLUX_TO_BLOOD,
            TransportRoute.BILIARY_EFFLUX,
            TransportRoute.RENAL_EFFLUX_TO_URINE,
            TransportRoute.TUBULAR_REABSORPTION,
        }:
            if self.source_unbound_fraction is None:
                raise ValueError(
                    f"{self.name}: tissue-source route requires source_unbound_fraction"
                )
            if not 0.0 < self.source_unbound_fraction <= 1.0:
                raise ValueError(
                    f"{self.name}: source_unbound_fraction must be in (0,1]"
                )
        elif self.source_unbound_fraction is not None:
            if not 0.0 < self.source_unbound_fraction <= 1.0:
                raise ValueError(
                    f"{self.name}: source_unbound_fraction must be in (0,1]"
                )
        if not self.source_id:
            raise ValueError(f"{self.name}: source_id cannot be blank")

    def to_dict(self) -> dict:
        value = asdict(self)
        value["route"] = TransportRoute(self.route).value
        return value


@dataclass(frozen=True)
class TransportFlux:
    process: str
    route: str
    source: str
    sink: str
    source_unbound_concentration: float
    requested_amount: float
    transferred_amount: float

    def to_dict(self) -> dict:
        return asdict(self)


def michaelis_menten_rate(
    unbound_concentration: float,
    *,
    vmax_amount_per_h: float,
    km_concentration: float,
) -> float:
    if unbound_concentration < 0:
        raise ValueError("unbound_concentration cannot be negative")
    if vmax_amount_per_h < 0:
        raise ValueError("Vmax cannot be negative")
    if km_concentration <= 0:
        raise ValueError("Km must be positive")
    if unbound_concentration == 0 or vmax_amount_per_h == 0:
        return 0.0
    return float(
        vmax_amount_per_h
        * unbound_concentration
        / (km_concentration + unbound_concentration)
    )


def _route_endpoints(route: TransportRoute) -> tuple[str, str]:
    mapping = {
        TransportRoute.HEPATIC_UPTAKE: ("central", "liver"),
        TransportRoute.HEPATIC_EFFLUX_TO_BLOOD: ("liver", "central"),
        TransportRoute.BILIARY_EFFLUX: ("liver", "eliminated"),
        TransportRoute.RENAL_UPTAKE: ("central", "kidney"),
        TransportRoute.RENAL_EFFLUX_TO_URINE: ("kidney", "eliminated"),
        TransportRoute.TUBULAR_REABSORPTION: ("kidney", "central"),
    }
    return mapping[route]


def _source_unbound_concentration(
    process: TransporterProcess,
    *,
    source: str,
    central_amount: float,
    tissue_amounts: Mapping[str, float],
    physiology: Physiology,
    plasma_unbound_fraction: float,
    blood_to_plasma_ratio: float,
) -> float:
    if source == "central":
        blood_concentration = central_amount / physiology.central_volume_l
        return float(
            blood_concentration
            * plasma_unbound_fraction
            / blood_to_plasma_ratio
        )

    tissue = physiology.tissue_map[source]
    total_concentration = tissue_amounts[source] / tissue.volume_l
    return float(total_concentration * float(process.source_unbound_fraction))


def apply_transporter_step(
    *,
    central_amount: float,
    tissue_amounts: Mapping[str, float],
    eliminated_amount: float,
    physiology: Physiology,
    processes: tuple[TransporterProcess, ...],
    plasma_unbound_fraction: float,
    blood_to_plasma_ratio: float,
    dt_h: float,
) -> tuple[float, dict[str, float], float, tuple[TransportFlux, ...]]:
    """Apply all transporter routes simultaneously for one operator step."""

    if dt_h < 0:
        raise ValueError("dt_h cannot be negative")
    if not 0.0 < plasma_unbound_fraction <= 1.0:
        raise ValueError("plasma_unbound_fraction must be in (0,1]")
    if blood_to_plasma_ratio <= 0:
        raise ValueError("blood_to_plasma_ratio must be positive")

    tissues = dict(tissue_amounts)
    for process in processes:
        process.validate()
        route = TransportRoute(process.route)
        source, sink = _route_endpoints(route)
        if source not in {"central", *physiology.tissue_map.keys()}:
            raise ValueError(f"{process.name}: unknown source compartment {source}")
        if sink not in {"central", "eliminated", *physiology.tissue_map.keys()}:
            raise ValueError(f"{process.name}: unknown sink compartment {sink}")

    if not processes or dt_h == 0:
        return central_amount, tissues, eliminated_amount, ()

    requests = []
    source_totals: dict[str, float] = {}
    for process in processes:
        route = TransportRoute(process.route)
        source, sink = _route_endpoints(route)
        concentration = _source_unbound_concentration(
            process,
            source=source,
            central_amount=central_amount,
            tissue_amounts=tissues,
            physiology=physiology,
            plasma_unbound_fraction=plasma_unbound_fraction,
            blood_to_plasma_ratio=blood_to_plasma_ratio,
        )
        requested = michaelis_menten_rate(
            concentration,
            vmax_amount_per_h=process.vmax_amount_per_h,
            km_concentration=process.km_concentration,
        ) * dt_h
        requests.append((process, source, sink, concentration, requested))
        source_totals[source] = source_totals.get(source, 0.0) + requested

    available = {"central": float(central_amount), **{k: float(v) for k, v in tissues.items()}}
    scales = {
        source: (
            1.0
            if requested <= available[source] or requested <= 0
            else available[source] / requested
        )
        for source, requested in source_totals.items()
    }

    central = float(central_amount)
    eliminated = float(eliminated_amount)
    updated = dict(tissues)
    fluxes = []

    for process, source, sink, concentration, requested in requests:
        transferred = float(requested * scales[source])

        if source == "central":
            central -= transferred
        else:
            updated[source] -= transferred

        if sink == "central":
            central += transferred
        elif sink == "eliminated":
            eliminated += transferred
        else:
            updated[sink] += transferred

        fluxes.append(
            TransportFlux(
                process=process.name,
                route=TransportRoute(process.route).value,
                source=source,
                sink=sink,
                source_unbound_concentration=concentration,
                requested_amount=float(requested),
                transferred_amount=transferred,
            )
        )

    # Guard only against floating-point roundoff; meaningful negativity is a bug.
    if central < -1e-10 or any(value < -1e-10 for value in updated.values()):
        raise RuntimeError("transporter operator produced negative compartment amount")
    central = max(central, 0.0)
    updated = {name: max(value, 0.0) for name, value in updated.items()}

    before = central_amount + sum(tissue_amounts.values()) + eliminated_amount
    after = central + sum(updated.values()) + eliminated
    if not np.isclose(before, after, rtol=0.0, atol=1e-10):
        raise RuntimeError(
            f"transporter mass balance failure: before={before} after={after}"
        )

    return central, updated, eliminated, tuple(fluxes)
