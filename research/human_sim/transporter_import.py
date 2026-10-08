"""Import provenance-tagged transporter kinetic processes for HumanSim.

CSV columns:
    name,route,vmax_amount_per_h,km_concentration,
    source_unbound_fraction,source_id,transporter_family

source_unbound_fraction may be blank for blood/plasma-source routes and is required
for tissue-source efflux/reabsorption routes.
"""

from __future__ import annotations

import csv
from pathlib import Path

from research.human_sim.transporters import TransporterProcess


def load_transporter_csv(path: str | Path) -> tuple[TransporterProcess, ...]:
    path = Path(path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("transporter CSV contains no rows")

    required = {
        "name",
        "route",
        "vmax_amount_per_h",
        "km_concentration",
        "source_unbound_fraction",
        "source_id",
        "transporter_family",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"transporter CSV missing columns: {sorted(missing)}")

    processes = []
    seen = set()
    for row in rows:
        name = row["name"].strip()
        if not name:
            raise ValueError("transporter process name cannot be blank")
        if name in seen:
            raise ValueError(f"duplicate transporter process name: {name}")
        seen.add(name)

        source_fraction_text = row["source_unbound_fraction"].strip()
        source_fraction = (
            None if source_fraction_text == "" else float(source_fraction_text)
        )

        process = TransporterProcess(
            name=name,
            route=row["route"].strip(),
            vmax_amount_per_h=float(row["vmax_amount_per_h"]),
            km_concentration=float(row["km_concentration"]),
            source_unbound_fraction=source_fraction,
            source_id=row["source_id"].strip(),
            transporter_family=row["transporter_family"].strip(),
        )
        process.validate()
        processes.append(process)

    return tuple(processes)
