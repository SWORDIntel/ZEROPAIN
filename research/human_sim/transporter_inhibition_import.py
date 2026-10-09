"""Import competitive transporter-inhibition metadata for multi-ligand HumanSim.

CSV columns:
    inhibitor_name,interaction_group,ki_concentration,source_compartment,
    source_unbound_fraction,source_id,mode

source_unbound_fraction may be blank when source_compartment=central and is required
for tissue-source inhibition.
"""

from __future__ import annotations

import csv
from pathlib import Path

from research.human_sim.transporter_competition import TransporterInhibition


def load_transporter_inhibition_csv(
    path: str | Path,
) -> dict[str, tuple[TransporterInhibition, ...]]:
    path = Path(path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("transporter inhibition CSV contains no rows")

    required = {
        "inhibitor_name",
        "interaction_group",
        "ki_concentration",
        "source_compartment",
        "source_unbound_fraction",
        "source_id",
        "mode",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(
            f"transporter inhibition CSV missing columns: {sorted(missing)}"
        )

    by_ligand: dict[str, list[TransporterInhibition]] = {}
    seen: set[tuple[str, str]] = set()

    for row in rows:
        inhibitor_name = row["inhibitor_name"].strip()
        interaction_group = row["interaction_group"].strip()
        key = (inhibitor_name, interaction_group)
        if key in seen:
            raise ValueError(
                f"duplicate inhibitor/group entry: {inhibitor_name}/{interaction_group}"
            )
        seen.add(key)

        fraction_text = row["source_unbound_fraction"].strip()
        fraction = None if fraction_text == "" else float(fraction_text)

        inhibition = TransporterInhibition(
            inhibitor_name=inhibitor_name,
            interaction_group=interaction_group,
            ki_concentration=float(row["ki_concentration"]),
            source_compartment=row["source_compartment"].strip() or "central",
            source_unbound_fraction=fraction,
            source_id=row["source_id"].strip(),
            mode=row["mode"].strip() or "competitive",
        )
        inhibition.validate()
        by_ligand.setdefault(inhibitor_name, []).append(inhibition)

    return {
        ligand: tuple(values)
        for ligand, values in by_ligand.items()
    }
