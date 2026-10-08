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
    "synthetic_fixture": EvidenceSource(
        source_id="synthetic_fixture",
        title="Bundled synthetic HumanSim population fixture",
        kind="software_fixture",
        url="",
        citation="Repository test fixture only; not an external population dataset.",
        notes=(
            "Column-compatible with supported population imports but numerically "
            "fabricated for tests and CI."
        ),
    ),
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
    "loryan2022_kpuu": EvidenceSource(
        source_id="loryan2022_kpuu",
        title="Unbound Brain-to-Plasma Partition Coefficient, Kp,uu,brain",
        kind="journal_review",
        url="https://pubmed.ncbi.nlm.nih.gov/35411506/",
        citation=(
            "Loryan I et al. Pharm Res. 2022;39(7):1321-1341. "
            "doi:10.1007/s11095-022-03246-6"
        ),
        notes=(
            "Defines Kp,uu,brain as the unbound brain-to-plasma concentration ratio "
            "and emphasizes unbound exposure as the pharmacologically relevant quantity."
        ),
    ),
    "pang2019_clearance": EvidenceSource(
        source_id="pang2019_clearance",
        title="Hepatic clearance concepts and misconceptions",
        kind="journal_review",
        url="https://pubmed.ncbi.nlm.nih.gov/31398312/",
        citation=(
            "Pang KS et al. Biochem Pharmacol. 2019;168:56-62. "
            "doi:10.1016/j.bcp.2019.07.025"
        ),
        notes=(
            "Reviews the well-stirred and alternative hepatic-clearance models and "
            "their assumptions; HumanSim treats well-stirred clearance as a reference "
            "model rather than silently conflating it with tissue elimination."
        ),
    ),
    "httk_schmitt": EvidenceSource(
        source_id="httk_schmitt",
        title="httk Schmitt tissue partition implementation",
        kind="software_model",
        url="https://search.r-project.org/CRAN/refmans/httk/html/parameterize_schmitt.html",
        citation=(
            "httk implementation of Schmitt 2008 partitioning, modified/calibrated "
            "by Pearce et al. 2017."
        ),
        notes=(
            "predict_partitioning_schmitt returns tissue-to-unbound-plasma "
            "partition coefficients; these require multiplication by fu_plasma "
            "to obtain total tissue:total plasma Kp."
        ),
    ),
    "ich_m12_transporters": EvidenceSource(
        source_id="ich_m12_transporters",
        title="ICH M12 Drug Interaction Studies",
        kind="regulatory_guidance",
        url="https://www.fda.gov/regulatory-information/search-fda-guidance-documents/m12-drug-interaction-studies",
        citation="ICH M12 Drug Interaction Studies, FDA final guidance, August 2024.",
        notes=(
            "Highlights P-gp/BCRP, OATP1B1/1B3, OAT1/OAT3, OCT2, MATE1 and "
            "MATE2-K as major transporter systems for disposition/DDI evaluation."
        ),
    ),
    "giacomini2010_transporters": EvidenceSource(
        source_id="giacomini2010_transporters",
        title="Membrane transporters in drug development",
        kind="journal_review",
        url="https://pubmed.ncbi.nlm.nih.gov/20190787/",
        citation=(
            "Giacomini KM et al. Nat Rev Drug Discov. 2010;9(3):215-236. "
            "doi:10.1038/nrd3028"
        ),
        notes=(
            "International Transporter Consortium review describing clinically "
            "important uptake/efflux transporters in intestine, liver, kidney and barriers."
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
