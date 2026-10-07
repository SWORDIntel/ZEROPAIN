"""Source/provenance records for calibrated HumanSim parameters.

A source record is metadata, not permission to copy a source's data wholesale.
Numerical imports should retain the upstream dataset/version and the transform used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    title: str
    kind: str
    url: str
    citation: str
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


SOURCE_REGISTRY: Mapping[str, EvidenceSource] = {
    "httk_population": EvidenceSource(
        source_id="httk_population",
        title="httk virtual population generator",
        kind="software_dataset",
        url="https://cran.r-project.org/package=httk",
        citation=(
            "Ring CL, Pearce RG, Setzer RW, Wetmore BA, Wambaugh JF. "
            "Environment International. 2017;106:105-118. "
            "doi:10.1016/j.envint.2017.06.004"
        ),
        notes=(
            "Generates correlated demographic/physiological virtual individuals; "
            "direct-resampling mode uses NHANES-linked records."
        ),
    ),
    "httk_tissue": EvidenceSource(
        source_id="httk_tissue",
        title="httk tissue.data / physiology.data",
        kind="software_dataset",
        url="https://cran.r-project.org/package=httk",
        citation=(
            "httk tissue/physiology tables compile Birnbaum et al. 1994, "
            "ICRP reference data, Schmitt 2008, Ruark et al. 2014 and related sources."
        ),
        notes="Provides tissue composition, organ volumes and blood-flow parameters.",
    ),
    "pksim_population": EvidenceSource(
        source_id="pksim_population",
        title="PK-Sim human population physiological database",
        kind="software_dataset",
        url="https://docs.open-systems-pharmacology.org/",
        citation="Open Systems Pharmacology PK-Sim documentation and population database.",
        notes=(
            "Human anatomical/physiological parameters vary with age, sex, body weight "
            "and BMI; generated populations can be exported to CSV."
        ),
    ),
    "schmitt_partitioning": EvidenceSource(
        source_id="schmitt_partitioning",
        title="General approach for tissue:plasma partition coefficients",
        kind="journal",
        url="https://pubmed.ncbi.nlm.nih.gov/17981004/",
        citation="Schmitt W. Toxicol In Vitro. 2008;22(2):457-467.",
        notes=(
            "Partition coefficients are predicted from tissue composition plus "
            "compound-specific physicochemical/binding parameters."
        ),
    ),
}


def sources_dict(ids: tuple[str, ...] | list[str]) -> dict[str, dict]:
    unknown = [source_id for source_id in ids if source_id not in SOURCE_REGISTRY]
    if unknown:
        raise KeyError(f"unknown evidence source ids: {unknown}")
    return {source_id: SOURCE_REGISTRY[source_id].to_dict() for source_id in ids}
