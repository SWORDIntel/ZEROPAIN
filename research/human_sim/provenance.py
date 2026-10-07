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

    "icrp89": EvidenceSource(
        source_id="icrp89",
        title="ICRP Publication 89: Basic Anatomical and Physiological Data",
        kind="reference_compendium",
        url="https://www.icrp.org/publication.asp?id=icrp%20publication%2089",
        citation="ICRP Publication 89. Ann ICRP. 2002;32(3-4).",
        notes=(
            "Reference adult organ masses and tissue densities; adult male brain "
            "mass 1450 g and brain specific gravity approximately 1.04."
        ),
    ),
    "brown1997_pbpk": EvidenceSource(
        source_id="brown1997_pbpk",
        title="Physiological parameter values for physiologically based pharmacokinetic models",
        kind="journal_review",
        url="https://pubmed.ncbi.nlm.nih.gov/9249929/",
        citation=(
            "Brown RP, Delp MD, Lindstedt SL, Rhomberg LR, Beliles RP. "
            "Toxicol Ind Health. 1997;13(4):407-484. "
            "doi:10.1177/074823379701300401"
        ),
        notes=(
            "PBPK physiology review emphasizing physiological variability and "
            "consistency between cardiac output and regional organ flows."
        ),
    ),
    "atsdr_mann_pbpk": EvidenceSource(
        source_id="atsdr_mann_pbpk",
        title="Physiological Data Used in the Mann PBPK Model for Humans",
        kind="government_reference_table",
        url="https://www.ncbi.nlm.nih.gov/books/NBK591624/table/ch3.tab15/",
        citation="ATSDR Toxicological Profile for Arsenic, Table 3-15, 2007.",
        notes=(
            "70-kg human reference values including blood volume 5.222 L, "
            "cardiac output 5.29 L/min, hepatic flow 0.32 L/min, splanchnic "
            "flow 1.02 L/min, and kidney flow 0.95 L/min."
        ),
    ),
    "lassen1985_cbf": EvidenceSource(
        source_id="lassen1985_cbf",
        title="Normal average value of cerebral blood flow in younger adults is 50 ml/100 g/min",
        kind="journal",
        url="https://pubmed.ncbi.nlm.nih.gov/4030914/",
        citation=(
            "Lassen NA. J Cereb Blood Flow Metab. 1985;5(3):347-349. "
            "doi:10.1038/jcbfm.1985.48"
        ),
        notes="Reference average cerebral blood flow approximately 50 mL/100 g/min.",
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
