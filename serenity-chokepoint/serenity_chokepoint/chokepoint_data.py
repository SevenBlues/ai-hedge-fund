"""
Curated chokepoint universe for the Serenity framework.

Each :class:`Node` encodes the *structural* attributes that the Chokepoint
framework actually cares about — supply concentration, physical
irreplaceability, qualification cycle, information asymmetry, demand/supply
imbalance and asymmetric-payoff inputs — rather than backward-looking
accounting ratios.

IMPORTANT
---------
The figures below are *curated, illustrative estimates* hand-assembled from
public reporting on Serenity's theses (his X / Substack posts, the
singularityresearchfund and archetype-research write-ups, the semiconstocks
tracker, TrendForce/SemiAnalysis-style commentary and company filings as of
~May 2026). They are deliberately approximate and are meant to demonstrate the
*methodology*. They are NOT live financial data and NOT investment advice.
Replace / refresh them with ``serenity.tools`` live pulls before relying on any
number.

Field reference (most structural fields are normalised 0..1, 1 = strongest
chokepoint):
    layer              CPO/photonics supply-chain tier (1 = system .. 7 = feedstock)
    top3_share         combined revenue share of the top 1-3 suppliers (0..1)
    irreplaceability   physical / material-science substitution difficulty (0..1)
    qual_cycle_months  hyperscaler / NVIDIA qualification cycle length (months)
    qualified          already designed-in / qualified by a hyperscaler or NVDA
    market_cap_b       equity market cap, USD billions
    inst_ownership     institutional ownership fraction (0..1; low = undiscovered)
    analyst_coverage   number of covering sell-side analysts (low = undiscovered)
    demand_cagr        AI-driven CAGR of the node's *end market* (e.g. 0.6 = 60%)
    capacity_cagr      the node's realistic supply / capacity growth CAGR
    ramp_rev_mult      projected 2028-29 revenue vs today (x), if thesis plays out
    fwd_ev_sales       forward EV/Sales on ramped revenue (valuation stretch proxy)
    dilution_risk      ATM / SBC / equity-raise dilution risk (0..1)
    tech_path_risk     risk the node's tech path (e.g. CPO) loses to alternatives (0..1)
    insider_buying     recent net insider buying
    short_interest     short interest as fraction of float (0..1; squeeze fuel)
    ma_potential       likelihood of being acquired at a premium (0..1)
    vertical_integ     ability to capture adjacent layers / pricing power (0..1)
    depends_on         upstream tickers this node structurally depends on (graph edges)
    thesis             one-line chokepoint rationale
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Human-readable names for the supply-chain tiers (Serenity's 7+ layer teardown).
LAYERS = {
    1: "System / Hyperscaler",
    2: "Optical module / engine",
    3: "Laser / light source (CW, DFB, EML)",
    4: "Substrate / epitaxy (InP, GaAs, SOI)",
    5: "Materials / precursors / feedstock",
    6: "Test / qualification equipment",
    7: "Packaging / FAU / crucibles",
}


@dataclass
class Node:
    ticker: str
    name: str
    layer: int
    top3_share: float
    irreplaceability: float
    qual_cycle_months: int
    qualified: bool
    market_cap_b: float
    inst_ownership: float
    analyst_coverage: int
    demand_cagr: float
    capacity_cagr: float
    ramp_rev_mult: float
    fwd_ev_sales: float
    dilution_risk: float
    tech_path_risk: float
    insider_buying: bool = False
    short_interest: float = 0.0
    ma_potential: float = 0.0
    vertical_integ: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    thesis: str = ""


# ---------------------------------------------------------------------------
# Curated universe (~ May 2026). Tickers without a clean US listing are kept
# for the supply-chain GRAPH (dependency edges) but flagged non-investable via
# market_cap_b <= 0 so the screen skips them in the asymmetric-odds ranking.
# ---------------------------------------------------------------------------
UNIVERSE: list[Node] = [
    # ---- Layer 3: laser / light source — the CPO "external light source" choke
    Node(
        ticker="SIVE", name="Sivers Semiconductors", layer=3,
        top3_share=0.55, irreplaceability=0.80, qual_cycle_months=18, qualified=True,
        market_cap_b=0.29, inst_ownership=0.18, analyst_coverage=2,
        demand_cagr=0.70, capacity_cagr=0.25, ramp_rev_mult=6.0, fwd_ev_sales=4.0,
        dilution_risk=0.55, tech_path_risk=0.45,
        insider_buying=True, short_interest=0.06, ma_potential=0.70, vertical_integ=0.35,
        depends_on=["AXTI", "IQE"],
        thesis="CW laser light-source chokepoint for co-packaged optics; 2027-28 ramp; AVGO/MRVL buyout optionality.",
    ),
    Node(
        ticker="POET", name="POET Technologies", layer=3,
        top3_share=0.40, irreplaceability=0.70, qual_cycle_months=18, qualified=True,
        market_cap_b=0.55, inst_ownership=0.22, analyst_coverage=4,
        demand_cagr=0.65, capacity_cagr=0.30, ramp_rev_mult=5.0, fwd_ev_sales=6.0,
        dilution_risk=0.55, tech_path_risk=0.50,
        insider_buying=False, short_interest=0.12, ma_potential=0.45, vertical_integ=0.55,
        depends_on=["SIVE", "AXTI"],
        thesis="Optical interposer integrating lasers/modulators/electronics on one chip; small-cap CPO pure-play.",
    ),
    Node(
        ticker="LITE", name="Lumentum", layer=3,
        top3_share=0.45, irreplaceability=0.65, qual_cycle_months=15, qualified=True,
        market_cap_b=7.5, inst_ownership=0.92, analyst_coverage=18,
        demand_cagr=0.50, capacity_cagr=0.30, ramp_rev_mult=2.2, fwd_ev_sales=3.2,
        dilution_risk=0.20, tech_path_risk=0.30,
        ma_potential=0.10, vertical_integ=0.60,
        depends_on=["AXTI", "COHR"],
        thesis="Near-duopoly in high-power CW lasers for CPO alongside Coherent; established but already crowded.",
    ),

    # ---- Layer 2: optical modules / transceivers
    Node(
        ticker="AAOI", name="Applied Optoelectronics", layer=2,
        top3_share=0.30, irreplaceability=0.55, qual_cycle_months=12, qualified=True,
        market_cap_b=2.6, inst_ownership=0.55, analyst_coverage=9,
        demand_cagr=0.60, capacity_cagr=0.35, ramp_rev_mult=4.0, fwd_ev_sales=2.5,
        dilution_risk=0.45, tech_path_risk=0.40,
        insider_buying=True, short_interest=0.20, ma_potential=0.35, vertical_integ=0.75,
        depends_on=["SIVE", "AXTI", "LITE"],
        thesis="Vertically integrated laser->design->assembly transceiver maker; 10x optical ramp into H2'27.",
    ),
    Node(
        ticker="COHR", name="Coherent Corp.", layer=2,
        top3_share=0.40, irreplaceability=0.60, qual_cycle_months=15, qualified=True,
        market_cap_b=12.0, inst_ownership=0.90, analyst_coverage=20,
        demand_cagr=0.50, capacity_cagr=0.30, ramp_rev_mult=2.0, fwd_ev_sales=3.0,
        dilution_risk=0.25, tech_path_risk=0.30,
        ma_potential=0.05, vertical_integ=0.70,
        depends_on=["AXTI"],
        thesis="Transceiver + laser leader vertically integrating up toward InP substrate (not yet feedstock).",
    ),

    # ---- Layer 4: substrate / epitaxy — the "AI oil"
    Node(
        ticker="AXTI", name="AXT Inc.", layer=4,
        top3_share=0.75, irreplaceability=0.92, qual_cycle_months=24, qualified=True,
        market_cap_b=0.85, inst_ownership=0.45, analyst_coverage=4,
        demand_cagr=0.65, capacity_cagr=0.20, ramp_rev_mult=4.5, fwd_ev_sales=3.5,
        dilution_risk=0.35, tech_path_risk=0.20,
        insider_buying=True, short_interest=0.10, ma_potential=0.40, vertical_integ=0.80,
        depends_on=["VNP", "SHIN-ETSU"],
        thesis="Western InP-substrate chokepoint ('Strait of Hormuz' of photonics); vertically integrated feedstock.",
    ),
    Node(
        ticker="IQE", name="IQE plc", layer=4,
        top3_share=0.50, irreplaceability=0.75, qual_cycle_months=18, qualified=True,
        market_cap_b=0.35, inst_ownership=0.40, analyst_coverage=5,
        demand_cagr=0.55, capacity_cagr=0.25, ramp_rev_mult=3.0, fwd_ev_sales=2.0,
        dilution_risk=0.40, tech_path_risk=0.30,
        short_interest=0.08, ma_potential=0.45, vertical_integ=0.50,
        depends_on=["AXTI", "VNP"],
        thesis="Compound-semi epitaxy (GaAs/InP) wafer foundry feeding photonics & VCSEL supply chains.",
    ),
    Node(
        ticker="SOI", name="Soitec (proxy)", layer=4,
        top3_share=0.80, irreplaceability=0.85, qual_cycle_months=24, qualified=True,
        market_cap_b=3.5, inst_ownership=0.60, analyst_coverage=12,
        demand_cagr=0.45, capacity_cagr=0.20, ramp_rev_mult=2.5, fwd_ev_sales=3.0,
        dilution_risk=0.20, tech_path_risk=0.35,
        ma_potential=0.20, vertical_integ=0.55,
        depends_on=[],
        thesis="SOI substrate near-monopoly underpinning silicon-photonics waveguides.",
    ),
    Node(
        ticker="INPACT", name="IntelliEPI (proxy)", layer=4,
        top3_share=0.45, irreplaceability=0.70, qual_cycle_months=18, qualified=True,
        market_cap_b=0.25, inst_ownership=0.30, analyst_coverage=2,
        demand_cagr=0.55, capacity_cagr=0.22, ramp_rev_mult=3.0, fwd_ev_sales=2.2,
        dilution_risk=0.30, tech_path_risk=0.35,
        ma_potential=0.40, vertical_integ=0.40,
        depends_on=["VNP"],
        thesis="InP epi-wafer supplier; CEO publicly confirmed structural InP shortage in Q1'26.",
    ),

    # ---- Layer 5: materials / feedstock
    Node(
        ticker="VNP", name="5N Plus", layer=5,
        top3_share=0.70, irreplaceability=0.88, qual_cycle_months=18, qualified=True,
        market_cap_b=0.95, inst_ownership=0.50, analyst_coverage=4,
        demand_cagr=0.50, capacity_cagr=0.18, ramp_rev_mult=3.0, fwd_ev_sales=2.5,
        dilution_risk=0.25, tech_path_risk=0.20,
        insider_buying=True, short_interest=0.05, ma_potential=0.30, vertical_integ=0.45,
        depends_on=[],
        thesis="High-purity indium/gallium/germanium feedstock; upstream of every InP/GaAs wafer.",
    ),
    Node(
        ticker="MP", name="MP Materials", layer=5,
        top3_share=0.60, irreplaceability=0.80, qual_cycle_months=18, qualified=True,
        market_cap_b=4.5, inst_ownership=0.65, analyst_coverage=10,
        demand_cagr=0.40, capacity_cagr=0.20, ramp_rev_mult=2.5, fwd_ev_sales=4.0,
        dilution_risk=0.30, tech_path_risk=0.25,
        short_interest=0.12, ma_potential=0.15, vertical_integ=0.60,
        depends_on=[],
        thesis="Only scaled Western rare-earth chokepoint; national-security leverage vs China weaponisation.",
    ),

    # ---- Layer 6: test / qualification equipment
    Node(
        ticker="AEHR", name="Aehr Test Systems", layer=6,
        top3_share=0.65, irreplaceability=0.70, qual_cycle_months=15, qualified=True,
        market_cap_b=0.55, inst_ownership=0.55, analyst_coverage=4,
        demand_cagr=0.55, capacity_cagr=0.30, ramp_rev_mult=3.5, fwd_ev_sales=4.5,
        dilution_risk=0.20, tech_path_risk=0.40,
        insider_buying=False, short_interest=0.18, ma_potential=0.30, vertical_integ=0.35,
        depends_on=["AAOI", "COHR"],
        thesis="Wafer-level burn-in/test chokepoint qualifying photonics & SiC before volume ramp.",
    ),

    # ---- Layer 1/2: power & ASIC enablers
    Node(
        ticker="XFAB", name="X-FAB Silicon Foundries", layer=2,
        top3_share=0.35, irreplaceability=0.60, qual_cycle_months=18, qualified=True,
        market_cap_b=1.28, inst_ownership=0.45, analyst_coverage=5,
        demand_cagr=0.45, capacity_cagr=0.25, ramp_rev_mult=2.5, fwd_ev_sales=2.0,
        dilution_risk=0.25, tech_path_risk=0.35,
        ma_potential=0.30, vertical_integ=0.50,
        depends_on=["SOI"],
        thesis="EU specialty foundry: silicon-photonics + 800VDC power semis; EU CHIPS Act 2 catalyst.",
    ),
    Node(
        ticker="NVTS", name="Navitas Semiconductor", layer=2,
        top3_share=0.30, irreplaceability=0.55, qual_cycle_months=15, qualified=True,
        market_cap_b=1.1, inst_ownership=0.50, analyst_coverage=8,
        demand_cagr=0.55, capacity_cagr=0.35, ramp_rev_mult=3.0, fwd_ev_sales=5.0,
        dilution_risk=0.45, tech_path_risk=0.45,
        short_interest=0.22, ma_potential=0.35, vertical_integ=0.30,
        depends_on=[],
        thesis="GaN/SiC power for NVIDIA's 800VDC datacenter push; high-beta power-density chokepoint.",
    ),
    Node(
        ticker="MRVL", name="Marvell Technology", layer=1,
        top3_share=0.40, irreplaceability=0.55, qual_cycle_months=18, qualified=True,
        market_cap_b=70.0, inst_ownership=0.85, analyst_coverage=30,
        demand_cagr=0.45, capacity_cagr=0.30, ramp_rev_mult=2.0, fwd_ev_sales=8.0,
        dilution_risk=0.10, tech_path_risk=0.25,
        ma_potential=0.05, vertical_integ=0.70,
        depends_on=["SIVE", "POET", "COHR", "LITE"],
        thesis="CPO ASIC/DSP architect; consolidator (Celestial AI) — large-cap, low asymmetry but graph-central.",
    ),
    Node(
        ticker="NVDA", name="NVIDIA", layer=1,
        top3_share=0.85, irreplaceability=0.70, qual_cycle_months=0, qualified=True,
        market_cap_b=4100.0, inst_ownership=0.68, analyst_coverage=60,
        demand_cagr=0.55, capacity_cagr=0.40, ramp_rev_mult=1.6, fwd_ev_sales=18.0,
        dilution_risk=0.05, tech_path_risk=0.20,
        ma_potential=0.0, vertical_integ=0.85,
        depends_on=["MRVL", "COHR", "LITE", "AAOI"],
        thesis="The 'tuna' / system anchor. Sets demand for everything downstream but offers no asymmetry here.",
    ),

    # ---- Layer 7: packaging / crucibles (graph-only structural nodes)
    Node(
        ticker="SHIN-ETSU", name="Shin-Etsu Chemical (pBN)", layer=7,
        top3_share=0.85, irreplaceability=0.90, qual_cycle_months=24, qualified=True,
        market_cap_b=0.0, inst_ownership=0.0, analyst_coverage=0,
        demand_cagr=0.45, capacity_cagr=0.15, ramp_rev_mult=1.5, fwd_ev_sales=0.0,
        dilution_risk=0.0, tech_path_risk=0.15,
        depends_on=[],
        thesis="Single-vendor pyrolytic boron-nitride crucibles required to grow InP — deep structural choke (no clean small-cap listing).",
    ),
]


def get_universe() -> list[Node]:
    """Return the curated universe (a fresh list copy)."""
    return list(UNIVERSE)


def by_ticker() -> dict[str, Node]:
    return {n.ticker: n for n in UNIVERSE}
