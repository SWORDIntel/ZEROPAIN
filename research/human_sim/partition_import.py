"""Import externally predicted tissue partition coefficients.

Expected CSV columns:
    tissue,value,basis,source_id,method

Supported basis values:
    tissue_to_plasma
    tissue_to_unbound_plasma

The importer performs no chemistry prediction itself.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from research.human_sim.disposition_mechanisms import PartitionBasis


@dataclass(frozen=True)
class ExternalPartitionTable:
    tissue_partition_coefficients: Mapping[str, float]
    basis: PartitionBasis
    source_id: str
    method: str

    def to_dict(self) -> dict:
        return {
            "tissue_partition_coefficients": dict(self.tissue_partition_coefficients),
            "basis": self.basis.value,
            "source_id": self.source_id,
            "method": self.method,
        }


def load_partition_csv(path: str | Path) -> ExternalPartitionTable:
    path = Path(path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("partition CSV contains no rows")

    required = {"tissue", "value", "basis", "source_id", "method"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"partition CSV missing columns: {sorted(missing)}")

    basis_values = {row["basis"].strip() for row in rows}
    source_ids = {row["source_id"].strip() for row in rows}
    methods = {row["method"].strip() for row in rows}
    if len(basis_values) != 1:
        raise ValueError("partition CSV must use one partition basis")
    if len(source_ids) != 1 or "" in source_ids:
        raise ValueError("partition CSV must use one non-empty source_id")
    if len(methods) != 1 or "" in methods:
        raise ValueError("partition CSV must use one non-empty method")

    basis = PartitionBasis(next(iter(basis_values)))
    values = {}
    for row in rows:
        tissue = row["tissue"].strip().lower()
        if not tissue:
            raise ValueError("partition tissue cannot be blank")
        if tissue in values:
            raise ValueError(f"duplicate partition tissue: {tissue}")
        value = float(row["value"])
        if value <= 0:
            raise ValueError(f"{tissue}: partition value must be positive")
        values[tissue] = value

    return ExternalPartitionTable(
        tissue_partition_coefficients=values,
        basis=basis,
        source_id=next(iter(source_ids)),
        method=next(iter(methods)),
    )
